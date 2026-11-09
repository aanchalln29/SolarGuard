import os
import datetime
from django import forms
from django.contrib.auth.models import User
from PIL import Image

from .models import Installation, Panel, Inspection, MaintenanceIssue, MaintenanceLog, LayoutRevision
from .permissions import get_accessible_panels, get_accessible_installations, is_admin, get_user_role


class InstallationForm(forms.ModelForm):
    """
    User-friendly form for adding/editing a solar array installation.
    Keeps fields simple with plain language and sensible defaults.
    """
    class Meta:
        model = Installation
        fields = ['name', 'site_address', 'installation_type', 'install_date', 'overview_image']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Sunnyvale Home Rooftop Array',
                'required': True,
                'id': 'installationNameInput'
            }),
            'site_address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. 104 Garden Street, Sunnyvale',
                'required': True,
                'id': 'installationAddressInput'
            }),
            'installation_type': forms.Select(attrs={
                'class': 'form-select',
                'id': 'installationTypeSelect'
            }),
            'install_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'id': 'installationDateInput'
            }),
            'overview_image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/jpeg,image/png,image/jpg',
                'id': 'installationOverviewInput'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['install_date'].required = False
        self.fields['overview_image'].required = False


class TechnicianAssignForm(forms.Form):
    """
    Admin-only form to assign or reassign a certified technician to an installation.
    Validates strictly server-side that the selected user is indeed a Technician.
    """
    technician = forms.ModelChoiceField(
        queryset=User.objects.filter(profile__role='technician').order_by('username'),
        required=False,
        empty_label="-- Unassigned (No Technician) --",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'technicianSelect'})
    )

    def clean_technician(self):
        tech = self.cleaned_data.get('technician')
        if tech and getattr(tech, 'profile', None) and tech.profile.role != 'technician':
            raise forms.ValidationError("Invalid assignment: Selected user does not have a certified Technician profile.")
        return tech


class PanelForm(forms.ModelForm):
    """
    Panel registration form.
    Scoped to installations accessible to the user.
    """
    class Meta:
        model = Panel
        fields = ['serial_number', 'installation', 'site_location', 'install_date', 'last_cleaned_date']
        widgets = {
            'serial_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. MOD-REC-370-01',
                'required': True,
                'id': 'panelSerialInput'
            }),
            'installation': forms.Select(attrs={
                'class': 'form-select',
                'id': 'panelInstallationSelect'
            }),
            'site_location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Main Rooftop - East Array',
                'required': False,
                'id': 'panelLocationInput'
            }),
            'install_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'id': 'panelInstallDate'
            }),
            'last_cleaned_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'id': 'panelCleanDate'
            }),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['install_date'].required = False
        self.fields['last_cleaned_date'].required = False
        self.fields['site_location'].required = False

        if user:
            self.fields['installation'].queryset = get_accessible_installations(user)
        else:
            self.fields['installation'].queryset = Installation.objects.all()


class InspectionForm(forms.ModelForm):
    """
    Image inspection upload form.
    Strictly scopes panel selection to active (non-retired) panels accessible to the current user.
    Validates file format, size limits, and image decodability.
    """
    class Meta:
        model = Inspection
        fields = ['panel', 'image', 'notes']
        widgets = {
            'panel': forms.Select(attrs={
                'class': 'form-select form-select-lg',
                'required': True,
                'id': 'panelSelect'
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control form-control-lg',
                'accept': 'image/jpeg,image/png,image/jpg',
                'required': True,
                'id': 'imageInput',
                'onchange': 'previewImage(event)'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Optional field inspection notes (e.g. close-up of cell hotspot, drone photo pass)...',
                'id': 'inspectionNotes'
            }),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            qs = get_accessible_panels(user).exclude(status='retired')
        else:
            qs = Panel.objects.exclude(status='retired')
        self.fields['panel'].queryset = qs
        self.fields['panel'].label_from_instance = lambda obj: (
            f"{obj.permanent_id or obj.serial_number} — {obj.installation.name if obj.installation else 'Unlinked'} "
            f"(Row {obj.grid_row or '?'}, Col {obj.grid_col or '?'})"
        )

    def clean_panel(self):
        panel = self.cleaned_data.get('panel')
        if panel and panel.status == 'retired':
            raise forms.ValidationError("Retired panels cannot be inspected.")
        return panel

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            # 1. Validate file extension
            valid_extensions = ['.jpg', '.jpeg', '.png']
            ext = os.path.splitext(image.name)[1].lower()
            if ext not in valid_extensions:
                raise forms.ValidationError("Unsupported file type. Please upload a JPG, JPEG, or PNG photograph.")

            # 2. Validate max file size (10 MB limit)
            max_size = 10 * 1024 * 1024
            if image.size > max_size:
                raise forms.ValidationError("File size exceeds 10 MB limit. Please upload a smaller image.")

            # 3. Validate image integrity (Pillow decode check)
            try:
                image.file.seek(0)
                pil_img = Image.open(image.file)
                pil_img.verify()
                image.file.seek(0)
            except Exception:
                raise forms.ValidationError("The uploaded file is corrupt or not a readable photograph.")

        return image


class MaintenanceIssueForm(forms.ModelForm):
    """
    Maintenance work order creation form.
    Customers submit requests for their own panels with optional supporting photo.
    Technician assignment and status progression are handled server-side through RBAC.
    """
    confirm_duplicate = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'confirmDuplicateCheck'}),
        label="Confirm submission of additional work order for this panel"
    )

    class Meta:
        model = MaintenanceIssue
        fields = ['panel', 'title', 'description', 'supporting_photo', 'status', 'priority']
        widgets = {
            'panel': forms.Select(attrs={'class': 'form-select', 'id': 'issuePanelSelect'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Heavy Dust Clean-off Required', 'id': 'issueTitleInput'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Details on recommended action or inspection findings...', 'id': 'issueDescInput'}),
            'supporting_photo': forms.FileInput(attrs={'class': 'form-control', 'id': 'issuePhotoInput'}),
            'status': forms.Select(attrs={'class': 'form-select', 'id': 'issueStatusSelect'}),
            'priority': forms.Select(attrs={'class': 'form-select', 'id': 'issuePrioritySelect'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields['status'].required = False
        self.fields['priority'].required = False
        if user:
            self.fields['panel'].queryset = get_accessible_panels(user)
            self.fields['panel'].label_from_instance = lambda obj: (
                f"{obj.permanent_id or obj.serial_number} — {obj.installation.name if obj.installation else 'Unlinked'} "
                f"(Row {obj.grid_row or '?'}, Col {obj.grid_col or '?'})"
            )
            # If not admin, lock status to Open
            if not is_admin(user):
                self.fields['status'].choices = [('Open', 'Open')]
                self.fields['status'].widget = forms.HiddenInput()
                self.fields['status'].initial = 'Open'

    def clean_status(self):
        status = self.cleaned_data.get('status')
        if not self.user or not is_admin(self.user):
            return 'Open'
        return status or 'Open'

    def clean_priority(self):
        priority = self.cleaned_data.get('priority')
        return priority or 'Medium'

    def clean_supporting_photo(self):
        photo = self.cleaned_data.get('supporting_photo')
        if photo:
            valid_extensions = ['.jpg', '.jpeg', '.png']
            ext = os.path.splitext(photo.name)[1].lower()
            if ext not in valid_extensions:
                raise forms.ValidationError("Unsupported file type. Please upload a JPG, JPEG, or PNG photograph.")
            if photo.size > 10 * 1024 * 1024:
                raise forms.ValidationError("File size exceeds 10 MB limit.")
            try:
                photo.file.seek(0)
                pil_img = Image.open(photo.file)
                pil_img.verify()
                photo.file.seek(0)
            except Exception:
                raise forms.ValidationError("The uploaded file is corrupt or not a readable photograph.")
        return photo


class AdminTechnicianAssignForm(forms.Form):
    """
    Form for Administrators to assign or reassign a certified technician to a work order.
    Strictly validates that the assigned user has the 'technician' role.
    """
    technician = forms.ModelChoiceField(
        queryset=User.objects.filter(profile__role__iexact='technician').order_by('username'),
        required=True,
        empty_label="-- Select Certified Technician --",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'techSelect'})
    )
    priority = forms.ChoiceField(
        choices=MaintenanceIssue.PRIORITY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'prioritySelect'})
    )
    notes = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional dispatch / scheduling notes...', 'id': 'assignNotesInput'})
    )

    def clean_technician(self):
        tech = self.cleaned_data.get('technician')
        if not tech:
            raise forms.ValidationError("Please select a technician.")
        role = get_user_role(tech)
        if role != 'technician':
            raise forms.ValidationError("Selected user is not a certified technician.")
        return tech


class TechnicianResolutionForm(forms.Form):
    """
    Form for assigned technicians to resolve an active work order.
    Requires substantive resolution notes documenting corrective actions.
    """
    resolution_notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Provide detailed resolution summary: actions taken, cleaning agents or replacement parts used, and post-service visual check...',
            'id': 'resolutionNotesInput'
        }),
        required=True,
        min_length=10,
        error_messages={
            'required': 'Resolution notes are mandatory to resolve a work order.',
            'min_length': 'Please enter at least 10 characters detailing the resolution work performed.'
        }
    )


class MaintenanceActionForm(forms.ModelForm):
    """
    Technician action logging form for recorded repairs, washing, and parts replacement.
    """
    ACTION_CHOICES = [
        ('cleaning', 'Surface Cleaning & Wash'),
        ('repair', 'Cell / Glass Surface Repair'),
        ('replacement', 'Module / Bypass Diode Replacement'),
        ('inspection', 'Field Routine Inspection'),
        ('note', 'Field Work Notes'),
    ]

    action_type = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'actionTypeSelect'})
    )

    class Meta:
        model = MaintenanceLog
        fields = ['action_type', 'performed_at', 'notes']
        widgets = {
            'performed_at': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'id': 'actionDateInput'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Details of work performed (materials used, technician notes)...', 'id': 'actionNotesInput'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.initial.get('performed_at'):
            self.initial['performed_at'] = datetime.date.today().isoformat()


class LayoutReviewForm(forms.Form):
    """
    Form for certified technicians and administrators to verify or request changes on a draft layout revision.
    """
    DECISION_CHOICES = [
        ('verified', 'Approve & Mark as Verified Layout'),
        ('changes_requested', 'Request Layout Adjustments / Re-submission'),
    ]

    status = forms.ChoiceField(
        choices=DECISION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'reviewStatusSelect'})
    )
    review_notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Provide feedback on array geometry, module count, and verification details...',
            'id': 'reviewNotesInput'
        }),
        required=True
    )
