from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal
import decimal
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
    """
    Normalize cadastral reference for comparison.
    - Remove spaces, dashes
    - Convert to uppercase
    - Replace common OCR errors (O vs 0, I vs 1)
    """
    if not ref:
        return ""

    normalized = str(ref).upper().strip()
    # Remove spaces and dashes
    normalized = re.sub(r'[\s\-]+', '', normalized)

    # Note: We don't auto-replace O/0 or I/1 here to preserve original format
    # Instead we'll use fuzzy matching in the comparison
    return normalized


def fuzzy_match_catastral(ref1: str, ref2: str, threshold: float = 0.85) -> bool:
    """
    Fuzzy match two cadastral references.
    Returns True if they're similar enough to be considered the same.

    Strategy:
    1. Exact match after normalization
    2. Levenshtein distance similarity
    3. Partial match (first 14 chars, ignoring trailing differences)
    """
    if not ref1 or not ref2:
        return False

    norm1 = normalize_catastral_ref(ref1)
    norm2 = normalize_catastral_ref(ref2)

    # Exact match
    if norm1 == norm2:
        return True

    # Empty after normalization
    if not norm1 or not norm2:
        return False

    # Calculate Levenshtein distance similarity
    from difflib import SequenceMatcher
    similarity = SequenceMatcher(None, norm1, norm2).ratio()

    if similarity >= threshold:
        return True

    # Partial match: cadastral refs are typically 20 chars, but sometimes truncated
    # Match if first 14 characters match (the significant part)
    min_len = min(len(norm1), len(norm2))
    if min_len >= 14:
        if norm1[:14] == norm2[:14]:
            return True

    return False

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

            # Try exact match first
            matches = tax_by_catastral.get(ref, [])

            # If no exact match, try fuzzy matching
            if not matches and ref:
                for tax_ref, items in tax_by_catastral.items():
                    if fuzzy_match_catastral(ref, tax_ref):
                        matches = items
                        logger.info(f"Fuzzy matched cadastral refs: {ref} ~= {tax_ref}")
                        break

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
                try:
                    e_val_str = str(prop.get('declared_value', '0')).strip()
                    t_val_str = str(tax_prop.get('declared_value', '0')).strip()

                    # Skip comparison if either value is empty/missing
                    if not e_val_str or e_val_str == '':
                        e_val_str = '0'
                    if not t_val_str or t_val_str == '':
                        t_val_str = '0'

                    # Handle Spanish number format (comma as decimal separator)
                    e_val_str = e_val_str.replace('.', '').replace(',', '.')
                    t_val_str = t_val_str.replace('.', '').replace(',', '.')

                    e_val = Decimal(e_val_str)
                    t_val = Decimal(t_val_str)

                    # Only compare if both values are non-zero
                    if e_val > 0 and t_val > 0:
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
                except (ValueError, decimal.InvalidOperation) as e:
                    logger.warning(f"Could not compare declared values: {e}")

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
