"""
Management command to audit and remediate historical inspection records
saved while deep learning model inference was offline or unavailable.
"""
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from core.models import Inspection
from ml_engine.predictor import predict_fault, predict_degradation


class Command(BaseCommand):
    help = "Audit and remediate inspections recorded during AI model downtime."

    def add_arguments(self, parser):
        parser.add_argument(
            '--mode',
            type=str,
            choices=['audit', 'mark_offline', 'reevaluate'],
            default='audit',
            help="Operation mode: 'audit' (list affected), 'mark_offline' (set Unable to Assess), or 'reevaluate' (re-run CNN v3.0)."
        )
        parser.add_argument(
            '--ids',
            type=str,
            default=None,
            help="Comma-separated list of inspection IDs to target (default: all suspect records)."
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Simulate the remediation without committing database changes."
        )

    def handle(self, *args, **options):
        mode = options['mode']
        dry_run = options['dry_run']
        ids_arg = options['ids']

        if ids_arg:
            target_ids = [int(i.strip()) for i in ids_arg.split(',') if i.strip()]
            queryset = Inspection.objects.filter(id__in=target_ids).order_by('id')
        else:
            # Match records created when the model was offline
            from django.db.models import Q
            queryset = Inspection.objects.filter(
                Q(predicted_class__icontains='unavailable') |
                Q(model_identifier__icontains='unavailable') |
                (Q(confidence_score=0.0) & Q(predicted_class='Normal'))
            ).order_by('id')

        count = queryset.count()
        self.stdout.write(self.style.NOTICE(f"Found {count} suspect inspection record(s) matching downtime criteria."))

        if count == 0:
            self.stdout.write(self.style.SUCCESS("No suspect records found. Database is clean."))
            return

        self.stdout.write("=" * 75)
        self.stdout.write(f"{'ID':<6} {'Panel':<14} {'Class':<22} {'Conf':<8} {'Priority':<20} {'Image Exists'}")
        self.stdout.write("-" * 75)

        records_to_process = []
        for insp in queryset:
            img_path = insp.image.path if insp.image else None
            img_exists = os.path.exists(img_path) if img_path else False
            panel_id = insp.panel.permanent_id if insp.panel else "No Panel"
            self.stdout.write(
                f"{insp.id:<6} {panel_id:<14} {insp.predicted_class:<22} "
                f"{insp.confidence_score:<8.1f} {insp.maintenance_priority_level:<20} {str(img_exists)}"
            )
            records_to_process.append((insp, img_path, img_exists))

        self.stdout.write("=" * 75)

        if mode == 'audit':
            self.stdout.write(self.style.SUCCESS(
                f"Audit complete. Run with --mode mark_offline or --mode reevaluate to remediate."
            ))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN ACTIVE — No database changes will be committed."))

        with transaction.atomic():
            for insp, img_path, img_exists in records_to_process:
                orig_summary = f"Class={insp.predicted_class}, Conf={insp.confidence_score}%, Pri={insp.maintenance_priority_level}"

                if mode == 'mark_offline':
                    insp.predicted_class = 'AI Model Unavailable'
                    insp.confidence_score = 0.0
                    insp.maintenance_priority_level = 'Unable to Assess'
                    insp.review_status = 'flagged'
                    audit_note = f"\n[Audited & Remediated {timezone.now().strftime('%Y-%m-%d %H:%M')}: AI Model Unavailable / Unable to Assess. Prior: {orig_summary}]"
                    insp.notes = (insp.notes or "") + audit_note
                    if not dry_run:
                        insp.save()
                    self.stdout.write(self.style.SUCCESS(f"Record #{insp.id}: Marked as 'AI Model Unavailable' / 'Unable to Assess'."))

                elif mode == 'reevaluate':
                    if not img_exists or not img_path:
                        self.stdout.write(self.style.ERROR(
                            f"Record #{insp.id}: Image missing at '{img_path}'. Skipping re-evaluation."
                        ))
                        continue

                    self.stdout.write(f"Record #{insp.id}: Running MobileNetV2 CNN v3.0 inference on '{img_path}'...")
                    fault_res = predict_fault(img_path)

                    if fault_res.get('status') == 'model_unavailable':
                        self.stdout.write(self.style.ERROR(
                            f"Record #{insp.id}: Model unavailable during re-evaluation: {fault_res.get('error_message')}"
                        ))
                        continue

                    # Recompute priority
                    deg_res = predict_degradation(insp.panel, visual_finding=fault_res['predicted_class'])

                    insp.predicted_class = fault_res['predicted_class']
                    insp.confidence_score = fault_res['confidence_score']
                    insp.class_probabilities = fault_res.get('class_probabilities', {})
                    insp.maintenance_priority_score = deg_res.get('priority_score', 0)
                    insp.maintenance_priority_level = deg_res.get('priority_level', 'Unable to Assess')
                    insp.priority_explanation = deg_res.get('explanation_text', '')
                    insp.model_identifier = fault_res.get('engine', 'MobileNetV2 CNN v3.0')
                    insp.is_mock_prediction = False

                    if (fault_res.get('confidence_score', 0.0) < 60.0 or
                        fault_res.get('is_low_confidence') or
                        fault_res.get('is_uncertain')):
                        insp.review_status = 'flagged'
                    else:
                        insp.review_status = 'ai_predicted'

                    audit_note = (
                        f"\n[Remediated via MobileNetV2 v3.0 Re-evaluation on {timezone.now().strftime('%Y-%m-%d %H:%M')}: "
                        f"New Class={insp.predicted_class} ({insp.confidence_score}%), New Pri={insp.maintenance_priority_level}. "
                        f"Prior state: {orig_summary}]"
                    )
                    insp.notes = (insp.notes or "") + audit_note
                    if not dry_run:
                        insp.save()

                    self.stdout.write(self.style.SUCCESS(
                        f"Record #{insp.id}: Successfully re-evaluated -> {insp.predicted_class} ({insp.confidence_score}%), Priority: {insp.maintenance_priority_level}"
                    ))

            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("DRY RUN: All simulated changes rolled back."))
            else:
                self.stdout.write(self.style.SUCCESS(f"Remediation complete for {count} record(s)."))
