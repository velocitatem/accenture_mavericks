from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal
from enum import Enum
import re
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger("comparison")

class Severity(str, Enum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"

class IssueCode(str, Enum):
    MISSING_TAX_FORM = "MISSING_TAX_FORM"
    ORPHAN_TAX_FORM = "ORPHAN_TAX_FORM"
    CATASTRAL_MISMATCH = "CATASTRAL_MISMATCH"
    ADDRESS_MISMATCH = "ADDRESS_MISMATCH"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    DATE_MISMATCH = "DATE_MISMATCH"
    NOTARY_MISMATCH = "NOTARY_MISMATCH"
    SELLER_MISMATCH = "SELLER_MISMATCH"
    BUYER_MISMATCH = "BUYER_MISMATCH"
    VALUE_MISMATCH = "VALUE_MISMATCH"

    # Disabled for now
    # TAX_CALCULATION_ERROR = "TAX_CALCULATION_ERROR"

@dataclass
class Issue:
    code: IssueCode
    severity: Severity
    field: str
    escritura_value: Any
    tax_form_value: Any
    message: str
    form_id: Optional[str] = None

@dataclass
class PropertyComparisonReport:
    property_id: str
    ref_catastral: str
    status: Severity = Severity.OK
    matched_forms: List[str] = field(default_factory=list)
    issues: List[Dict[str, Any]] = field(default_factory=list)

    def add_issue(self, issue: Issue):
        self.issues.append({
            "code": issue.code.value,
            "severity": issue.severity.value,
            "field": issue.field,
            "escritura_value": str(issue.escritura_value),
            "tax_form_value": str(issue.tax_form_value),
            "message": issue.message,
            "form_id": issue.form_id,
        })
        if issue.severity == Severity.ERROR:
            self.status = Severity.ERROR
        elif issue.severity == Severity.WARNING and self.status == Severity.OK:
            self.status = Severity.WARNING

    def to_dict(self) -> Dict[str, Any]:
        return {
            "property_id": self.property_id,
            "ref_catastral": self.ref_catastral,
            "status": self.status.value,
            "matched_forms": self.matched_forms,
            "issues": self.issues,
        }

def normalize_catastral_ref(ref: str) -> str:
    return re.sub(r'\s+', '', str(ref).upper().strip())

def normalize_nif(nif: Optional[str]) -> str:
    if not nif: return ""
    return nif.upper().strip().replace('-', '').replace(' ', '')

def compare_escritura_with_tax_forms(data: Dict[str, List[Dict]]) -> List[Dict[str, Any]]:
    escrituras = data['escrituras']
    tax_forms = data['tax_forms']
    reports = []

    # Flatten tax form properties for easier comparison
    # Each tax form might have multiple properties
    tax_properties = []
    for form_idx, form in enumerate(tax_forms):
        form_id = form.get('document_number') or f"form_{form_idx}"
        for prop in form.get('properties', []):
            tax_properties.append({
                'form_id': form_id,
                'form_data': form,
                'property': prop
            })

    # Group tax properties by catastral ref
    tax_by_catastral = {}
    for item in tax_properties:
        ref = normalize_catastral_ref(item['property'].get('ref_catastral', ''))
        if ref:
            if ref not in tax_by_catastral:
                tax_by_catastral[ref] = []
            tax_by_catastral[ref].append(item)

    matched_refs = set()

    for escritura in escrituras:
        escritura_id = escritura.get('document_number', 'unk')
        for prop in escritura.get('properties', []):
            ref = normalize_catastral_ref(prop.get('ref_catastral', ''))
            prop_id = prop.get('id', 'unk')

            report = PropertyComparisonReport(
                property_id=f"{escritura_id}:{prop_id}",
                ref_catastral=ref
            )

            matches = tax_by_catastral.get(ref, [])
            if not matches:
                report.add_issue(Issue(
                    code=IssueCode.MISSING_TAX_FORM,
                    severity=Severity.ERROR,
                    field="ref_catastral",
                    escritura_value=ref,
                    tax_form_value=None,
                    message=f"No tax form found for property {ref}"
                ))
                reports.append(report.to_dict())
                continue

            report.matched_forms = [m['form_id'] for m in matches]
            matched_refs.add(ref)

            for match in matches:
                form = match['form_data']
                tax_prop = match['property']

                # Compare Date
                if escritura.get('date_of_sale') != form.get('date_of_sale'):
                    report.add_issue(Issue(
                        code=IssueCode.DATE_MISMATCH,
                        severity=Severity.ERROR,
                        field="date_of_sale",
                        escritura_value=escritura.get('date_of_sale'),
                        tax_form_value=form.get('date_of_sale'),
                        message="Date mismatch",
                        form_id=match['form_id']
                    ))

                # Compare Declared Value
                e_val = Decimal(str(prop.get('declared_value', 0)))
                t_val = Decimal(str(tax_prop.get('declared_value', 0)))
                if abs(e_val - t_val) > Decimal('0.01'):
                     report.add_issue(Issue(
                        code=IssueCode.VALUE_MISMATCH,
                        severity=Severity.ERROR,
                        field="declared_value",
                        escritura_value=e_val,
                        tax_form_value=t_val,
                        message="Declared value mismatch",
                        form_id=match['form_id']
                    ))

                # Compare Sellers (Check if all escritura sellers are in tax form)
                e_sellers = {normalize_nif(s.get('seller_nif') or s.get('nif')) for s in escritura.get('sellers', [])}
                t_sellers = {normalize_nif(s.get('seller_nif') or s.get('nif')) for s in form.get('sellers', [])}

                missing_sellers = e_sellers - t_sellers
                if missing_sellers:
                     report.add_issue(Issue(
                        code=IssueCode.SELLER_MISMATCH,
                        severity=Severity.ERROR,
                        field="sellers",
                        escritura_value=list(e_sellers),
                        tax_form_value=list(t_sellers),
                        message=f"Missing sellers in tax form: {missing_sellers}",
                        form_id=match['form_id']
                    ))

            reports.append(report.to_dict())

    # Check for orphans? (Optional, skipping for brevity as main goal is alignment)

    return reports

if __name__ == "__main__":
    import json
    from pathlib import Path
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    project_root = Path(__file__).parent.parent.parent
    ground_truths_dir = project_root / "ground-truths"

    try:
        with open(ground_truths_dir / "autoliquidacion_caso_real_completo.json", "r") as f:
            data_600 = json.load(f)
        with open(ground_truths_dir / "escritura_caso_real_completo.json", "r") as f:
            data_escritura = json.load(f)
        comparison_input = {
            'escrituras': [data_escritura],
            'tax_forms': [data_600] # The ground truth file seems to be a single object, so wrap in list
        }

        logger.info("Running comparison...")
        reports = compare_escritura_with_tax_forms(comparison_input)
        print(json.dumps(reports, indent=2, default=str))

    except Exception as e:
        logger.error(f"Comparison failed: {e}")
        import traceback
        traceback.print_exc()
