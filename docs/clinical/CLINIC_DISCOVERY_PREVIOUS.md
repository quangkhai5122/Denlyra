# Clinic design-partner field discovery

**Do not attach patient identifiers, health records, phone numbers, photos or images to public repositories or model conversations.** Use fictitious workflows and sanitized structural examples. Record clinic consent to research, limit data collection and identify information security owner.

## A. Administrative facts (requisite for legal scope)

- [ ] Official operating license type (dental specialist clinic, multi-specialty clinic, hospital, other)
- [ ] Location / oversight Sở Y tế / written EMR implementation instructions received
- [ ] Authorized inpatient/day/outpatient scope and permitted clinical services
- [ ] Name/title (not ID secrets) of legally responsible clinical director and EMR decision maker
- [ ] Clinic currently paper, electronic, hybrid; year and number of paper folders
- [ ] Reports/notifications expected from Sở Y tế and current EMR readiness assessments

## B. Record templates and signing

- [ ] All active paper templates photographed/scanned **without patient data**, form number and revision
- [ ] Mapping to 13/BV-01 or 16/BV-01, or other applicable officially approved form; clinical lead validates
- [ ] Lượt khám, treatment-plan, consent, procedure, prescription, image, finalization and archiving procedures
- [ ] When/whom does a clinician sign; patient/guardian signing situations
- [ ] Clinician's current lawful signature credentials/solutions and regulations applied
- [ ] Corrections to historical notes: current practice and approval authority
- [ ] Physical record custody, retention classifications, digitization rules and backup policy

## C. Operational workflows (observe at least one complete dry run)

- [ ] First visit: walk-in / phone / web booking → intake → exam → treatment estimate → finalization
- [ ] Returning patient: search history → restore chart → note → payment → next appointment
- [ ] Orthodontics: approved plan + installments + repeating visit + reschedule + treatment revision
- [ ] Prosthetics/implant: lab orders, imaging, material/implant lot, delivery/receipt, follow-up
- [ ] Refunds, discounts, missed visits, cancelled procedure and contested bills
- [ ] Patient/guardian communication via phone, Zalo and portal; administrative vs clinical messages
- [ ] Employee handoff between receptionist, chair assistant, dentist, coordinator and cashier

## D. Real technical environment

- [ ] Number of rooms/chairs, workstations/tablets, printers, label scanners and available Wi-Fi
- [ ] Internet uptime observed, outage playbook and clinical business continuity process
- [ ] X-ray, panoramic, CBCT, intraoral camera/scanner models; DICOM support and export options
- [ ] Existing vendor software/data ownership/export (CSV/SQL/PDF/DICOM) and contracts
- [ ] Current backup method, frequency, who tests restore, device/disk encryption
- [ ] Payment/e-invoice service and willingness to support approved integration

## E. Product validation with staff

- [ ] Ask staff to demonstrate 5 slowest steps (time them); do not rely on general feature requests
- [ ] Ask 'Which data do you retype? Which decisions cannot be reconstructed?'
- [ ] Ask about duplicated and lost paper files, appointment conflicts and treatment-lab coordination
- [ ] Ask who would buy, what switching anxiety exists, and whether a paid pilot is viable
- [ ] Rate clinic-specific EMR deadline/compliance risk with counsel
- [ ] Obtain 3 to 5 fully synthetic end-to-end acceptance scenarios validated by clinicians

## F. Field notes template

```
Clinic pseudonym / observation date / observed roles:
License scope confirmed? Source/approval method:
Record template list / form revision / professional owner:
Workflow ID and timestamped steps:
Current tools (paper, software, chat, spreadsheet):
Longest step and measured duration:
Failure mode and evidence (without PHI):
Safety-sensitive decision requiring a human clinician:
What information would be lost if switching software:
External services/devices and export format:
Candidate feature, benefit, expected daily frequency:
Named open regulatory question for legal advisor:
Clinician validation and approval date:
```
