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
    SUPERFICIE_MISMATCH = "SUPERFICIE_MISMATCH"
    VALOR_CATASTRAL_MISMATCH = "VALOR_CATASTRAL_MISMATCH"
    USO_MISMATCH = "USO_MISMATCH"
    CUOTA_MISMATCH = "CUOTA_MISMATCH"
    PROTOCOL_MISMATCH = "PROTOCOL_MISMATCH"
    DOCUMENT_NUMBER_MISMATCH = "DOCUMENT_NUMBER_MISMATCH"
    SALE_BREAKDOWN_MISMATCH = "SALE_BREAKDOWN_MISMATCH"

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

def normalize_text(text: Optional[str]) -> str:
    if not text: return ""
    return re.sub(r'\s+', ' ', str(text).upper().strip())

def normalize_date(date_str: Optional[str]) -> str:
    if not date_str: return ""
    date_str = str(date_str).strip()
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d.%m.%Y'):
        try:
            return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return date_str

def parse_decimal(val: Any) -> Optional[Decimal]:
    if val is None or val == '': return None
    val_str = str(val).strip()
    # detect format: if has both . and , use Spanish (1.234,56), else standard
    if ',' in val_str and '.' in val_str:
        val_str = val_str.replace('.', '').replace(',', '.')
    elif ',' in val_str:
        val_str = val_str.replace(',', '.')
    try:
        return Decimal(val_str)
    except decimal.InvalidOperation:
        return None

def compare_decimals(v1: Any, v2: Any, tolerance: Decimal = Decimal('0.01')) -> bool:
    d1, d2 = parse_decimal(v1), parse_decimal(v2)
    if d1 is None or d2 is None: return True  # skip if either missing
    if d1 == 0 or d2 == 0: return True  # skip zero comparisons
    return abs(d1 - d2) <= tolerance

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
                fid = match['form_id']

                # Date comparison with normalization
                e_date, t_date = normalize_date(escritura.get('date_of_sale')), normalize_date(form.get('date_of_sale'))
                if e_date and t_date and e_date != t_date:
                    report.add_issue(Issue(IssueCode.DATE_MISMATCH, Severity.ERROR, "date_of_sale",
                        escritura.get('date_of_sale'), form.get('date_of_sale'), "Date mismatch", fid))

                # Declared value
                if not compare_decimals(prop.get('declared_value'), tax_prop.get('declared_value')):
                    report.add_issue(Issue(IssueCode.VALUE_MISMATCH, Severity.ERROR, "declared_value",
                        prop.get('declared_value'), tax_prop.get('declared_value'), "Declared value mismatch", fid))

                # Sellers
                e_sellers = {normalize_nif(s.get('seller_nif') or s.get('nif')) for s in escritura.get('sellers', [])}
                t_sellers = {normalize_nif(s.get('seller_nif') or s.get('nif')) for s in form.get('sellers', [])}
                if missing := (e_sellers - t_sellers - {''}):
                    report.add_issue(Issue(IssueCode.SELLER_MISMATCH, Severity.ERROR, "sellers",
                        list(e_sellers), list(t_sellers), f"Missing sellers: {missing}", fid))

                # Buyers
                e_buyers = {normalize_nif(b.get('buyer_nif') or b.get('nif')) for b in escritura.get('buyers', [])}
                t_buyers = {normalize_nif(b.get('buyer_nif') or b.get('nif')) for b in form.get('buyers', [])}
                if missing := (e_buyers - t_buyers - {''}):
                    report.add_issue(Issue(IssueCode.BUYER_MISMATCH, Severity.ERROR, "buyers",
                        list(e_buyers), list(t_buyers), f"Missing buyers: {missing}", fid))

                # Notary info - handle nested dict or flat
                e_notary_raw = escritura.get('notary', {}).get('name') or escritura.get('notary_name')
                t_notary_raw = form.get('notary', {}).get('name') or form.get('notary_name')
                e_notary, t_notary = normalize_text(e_notary_raw), normalize_text(t_notary_raw)
                if e_notary and t_notary and e_notary != t_notary:
                    report.add_issue(Issue(IssueCode.NOTARY_MISMATCH, Severity.WARNING, "notary_name",
                        e_notary_raw, t_notary_raw, "Notary name mismatch", fid))

                # Protocol number
                e_proto = normalize_text(str(escritura.get('protocol_number', '')))
                t_proto = normalize_text(str(form.get('protocol_number', '')))
                if e_proto and t_proto and e_proto != t_proto:
                    report.add_issue(Issue(IssueCode.PROTOCOL_MISMATCH, Severity.ERROR, "protocol_number",
                        escritura.get('protocol_number'), form.get('protocol_number'), "Protocol number mismatch", fid))

                # Address
                e_addr = normalize_text(prop.get('address') or prop.get('direccion'))
                t_addr = normalize_text(tax_prop.get('address') or tax_prop.get('direccion'))
                if e_addr and t_addr and e_addr != t_addr:
                    from difflib import SequenceMatcher
                    if SequenceMatcher(None, e_addr, t_addr).ratio() < 0.8:
                        report.add_issue(Issue(IssueCode.ADDRESS_MISMATCH, Severity.WARNING, "address",
                            prop.get('address'), tax_prop.get('address'), "Address mismatch", fid))

                # Property type/uso
                e_type = normalize_text(prop.get('type') or prop.get('uso'))
                t_type = normalize_text(tax_prop.get('type') or tax_prop.get('uso'))
                if e_type and t_type and e_type != t_type:
                    report.add_issue(Issue(IssueCode.TYPE_MISMATCH, Severity.WARNING, "type",
                        prop.get('type'), tax_prop.get('type'), "Property type mismatch", fid))

                # Property type code (600U, 600R, etc)
                e_ptype = prop.get('property_type')
                t_ptype = tax_prop.get('property_type')
                if e_ptype and t_ptype and str(e_ptype) != str(t_ptype):
                    report.add_issue(Issue(IssueCode.TYPE_MISMATCH, Severity.ERROR, "property_type",
                        e_ptype, t_ptype, "Property type code mismatch", fid))

                # Superficie (any of the variants)
                for sup_key in ['surface_area', 'superficie', 'superficie_construida', 'superficie_util']:
                    e_sup, t_sup = prop.get(sup_key), tax_prop.get(sup_key)
                    if e_sup and t_sup and not compare_decimals(e_sup, t_sup, Decimal('1')):
                        report.add_issue(Issue(IssueCode.SUPERFICIE_MISMATCH, Severity.WARNING, sup_key,
                            e_sup, t_sup, f"{sup_key} mismatch", fid))
                        break

                # Valor catastral
                if not compare_decimals(prop.get('valor_catastral'), tax_prop.get('valor_catastral')):
                    report.add_issue(Issue(IssueCode.VALOR_CATASTRAL_MISMATCH, Severity.WARNING, "valor_catastral",
                        prop.get('valor_catastral'), tax_prop.get('valor_catastral'), "Cadastral value mismatch", fid))

                # Cuota/participacion - check ownership_distribution if present
                e_dist = prop.get('ownership_distribution', {})
                t_dist = tax_prop.get('ownership_distribution', {})
                if e_dist and t_dist:
                    for nif, e_pct in e_dist.items():
                        t_pct = t_dist.get(nif)
                        if t_pct is not None and not compare_decimals(e_pct, t_pct, Decimal('0.1')):
                            report.add_issue(Issue(IssueCode.CUOTA_MISMATCH, Severity.ERROR, f"ownership_{nif}",
                                e_pct, t_pct, f"Ownership share mismatch for {nif}", fid))

                # Document number mismatch (escritura vs tax form)
                e_docnum = escritura.get('document_number')
                t_docnum = form.get('document_number')
                if e_docnum and t_docnum and str(e_docnum) != str(t_docnum):
                    report.add_issue(Issue(IssueCode.DOCUMENT_NUMBER_MISMATCH, Severity.WARNING, "document_number",
                        e_docnum, t_docnum, "Document numbers differ between escritura and tax form", fid))

                # Sale breakdown comparison
                prop_id = prop.get('id')
                if prop_id:
                    e_by_seller = {s['seller_nif']: parse_decimal(s.get('percentage_sold')) for s in escritura.get('sale_breakdown', []) if s.get('property_id') == prop_id}
                    t_by_seller = {s['seller_nif']: parse_decimal(s.get('percentage_sold')) for s in form.get('sale_breakdown', []) if s.get('property_id') == prop_id}

                    for seller, e_pct in e_by_seller.items():
                        t_pct = t_by_seller.get(seller)
                        if e_pct and t_pct and abs(e_pct - t_pct) > Decimal('0.1'):
                            report.add_issue(Issue(IssueCode.SALE_BREAKDOWN_MISMATCH, Severity.ERROR, f"sale_pct_{seller}",
                                str(e_pct), str(t_pct), f"Sale percentage mismatch for seller {seller}", fid))

            reports.append(report.to_dict())

    # Check for orphan tax properties (in tax form but not in any escritura)
    for tax_ref, items in tax_by_catastral.items():
        if tax_ref not in matched_refs:
            for item in items:
                report = PropertyComparisonReport(
                    property_id=f"orphan:{item['form_id']}",
                    ref_catastral=tax_ref
                )
                report.add_issue(Issue(
                    code=IssueCode.ORPHAN_TAX_FORM,
                    severity=Severity.WARNING,
                    field="ref_catastral",
                    escritura_value=None,
                    tax_form_value=tax_ref,
                    message=f"Tax form property {tax_ref} has no matching escritura",
                    form_id=item['form_id']
                ))
                reports.append(report.to_dict())

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
