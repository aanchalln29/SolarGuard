# SolarGuard — Brand and Product Experience Guidelines

**Status:** Proposed design direction for review, not an approved final visual identity.

## 1. Brand foundation
**Name:** SolarGuard  
**Descriptor:** AI-Assisted Solar Panel Inspection & Maintenance  
**Purpose:** Make solar panel inspections understandable, actionable, and trackable for individual owners and professional maintenance teams.

### Brand attributes
Trustworthy, practical, calm, technically credible, approachable, modern, precise.

### Brand promise
Help users understand **visible** solar panel conditions, document maintenance, and decide what to check next — without overstating AI certainty.

### Messaging rules
- Say **"visible condition assessment"**, **"AI-assisted inspection"**, and **"maintenance priority"** when accurate.
- Do not say **"guaranteed defect detection"**, **"electrical safety certified"**, **"predicts remaining panel lifespan"**, or **"measures efficiency loss from a photo"**.
- Use clear, short sentences; explain technical terms when they first appear.
- Never blame users for blurry images or missing panel details; provide corrective guidance.
- Clearly distinguish **AI finding**, **user-confirmed maintenance action**, and **unverified recommendation**.

## 2. Audience-specific UX
### Individual solar owner
- Quick path: choose installation (or create one) → upload photo → understandable result → recommended next action → save history.
- Avoid requiring serial number, precise panel specifications, or technical measurements when unavailable.
- Use everyday language with optional detail for curious users.

### Professional maintenance user
- Efficient path: select site/panel → upload inspection → triage open issues → record action → verify follow-up.
- Support dense tables, filters, consistent statuses, and site-level views without clutter.
- Preserve inspection timestamps and auditability.

## 3. Visual direction (proposal)
Aim for an elegant, clean, mature utility-product interface — **not** a flashy AI landing page. Prioritize legibility, restrained accents, and purposeful information hierarchy.

### Suggested palette (to validate with UI prototypes)
| Token | Hex | Usage |
|---|---|---|
| `canvas` | `#F7F9F6` | Main light background |
| `surface` | `#FFFFFF` | Cards and forms |
| `ink` | `#192B27` | Primary text |
| `muted` | `#60736C` | Secondary text |
| `primary` | `#176B52` | Primary actions, active navigation |
| `primary-hover` | `#11513E` | Hover/focus action state |
| `accent` | `#D6A545` | Limited solar-inspired emphasis |
| `border` | `#DCE5DF` | Dividers and input borders |
| `danger` | `#B23B3B` | Errors and critical issues |
| `warning` | `#A96B12` | Caution states |
| `success` | `#267A53` | Confirmed completed states |

Colors are proposals, not strict mandates. Verify WCAG contrast for text and controls. Never convey status by color alone.

### Typography
- Prefer a readable system UI sans-serif stack (`system-ui`, `Segoe UI`, `Arial`, sans-serif) until a specific font is approved.
- Distinct headings, readable body text, aligned numbers for scores and dates.
- Avoid oversized hero text, decorative typography, and tiny metadata.

### Components
- Calm navigation, clear page titles, straightforward forms, compact summary cards, usable tables, accessible charts.
- Consistent spacing and border radii; minimal shadows; no gratuitous gradients, glowing orbs, glass effects, or decorative animation.
- Use icons sparingly, always with accessible text labels for critical actions.
- Responsive layouts for laptop, tablet, and phone; field users may upload from phones even though v1 is a web application.

## 4. Information architecture
### Shared areas
- Overview / Dashboard
- Installations / Sites
- Inspections
- Maintenance
- Account / Settings

### Owner-focused interface
Simple home view: latest inspection, open maintenance items, quick upload, recent history.

### Professional interface
Site switcher, searchable panel list, open issues queue, inspection trends, maintenance logs.

Avoid adding unrelated pages, testimonials, pricing, fake live statistics, or decorative marketing sections to the operational application.

## 5. Inspection result design
The result should answer in this order:
1. **What did SolarGuard observe?** (e.g., “Possible dust accumulation”)
2. **How certain is the model?** Show a score only if its meaning is established; do not treat softmax output as automatically calibrated probability.
3. **What should I do next?** Practical, appropriately cautious advice.
4. **What are the limits?** “Image inspection cannot verify electrical safety or performance.”
5. **What can I record?** Create issue, add note, log maintenance, schedule/revisit follow-up.

### Example wording
- Normal: “No supported visible fault detected in this image.” Never “Panel is perfectly healthy.”
- Dusty: “Possible dust buildup. Consider a safe inspection or cleaning by a qualified person.”
- Cracked: “Possible visible cracking. Avoid handling damaged electrical equipment; arrange professional inspection.”
- Bird-Dropping: “Possible bird droppings on the surface. Consider appropriate cleaning and a follow-up image.”
- Uncertain: “We couldn't assess this image reliably. Try a clear, well-lit photo of one panel.”

Do not encourage users to climb onto roofs or handle live electrical equipment.

## 6. Status and risk communication
Keep three concepts visually and semantically distinct:
- **Visual finding:** Normal / Dusty / Cracked / Bird-Dropping / Unable to assess (subject to dataset approval).
- **Maintenance workflow:** Open / In progress / Resolved / Needs review.
- **Maintenance priority:** Informational / Review soon / Professional attention recommended (if an approved rules engine exists).

Never present maintenance priority as a scientifically validated degradation probability. Do not show fabricated percentages, cost savings, energy loss, or model accuracy.

## 7. Interaction and accessibility
- Clear loading, success, empty, failure, and retry states.
- Accessible labels, keyboard navigation, visible focus, descriptive errors, and meaningful alt text.
- Validate image type and size before processing; offer upload guidance.
- Support mobile photo selection without forcing a dedicated app.
- Confirm destructive actions; avoid accidental deletion of inspection history.
- Charts require text summaries or accessible tabular alternatives.

## 8. Data trust and privacy
- Make it clear whether uploaded images are stored and who can see them.
- Do not show another user's panel photos, site names, or maintenance records.
- Provide a privacy-conscious default; agree on image retention before deployment.
- Use real application data, never placeholder values presented as actual inspections.

## 9. Design deliverables and review gate
Before coding the complete UI, create a small prototype covering:
1. Owner dashboard
2. Professional site dashboard
3. Image upload flow
4. Inspection result (including uncertain/error states)
5. Maintenance issue detail/history

Present desktop and mobile layouts and ask the owner to approve the palette, typography, navigation, and result wording. After approval, translate decisions into design tokens and reusable components.

## 10. Brand guardrail for Antigravity
Do not invent a logo, tagline, customer testimonials, claims of detection accuracy, or commercial features without approval. Keep the visual system consistent, accessible, restrained, and credible. Prioritize the real product workflow over decorative presentation.
