from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal
from enum import Enum
import re
from dataclasses import dataclass, field
from datetime import datetime


class Severity(str, Enum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


class IssueCode(str, Enum):
    MISSING_TAX_FORM = "MISSING_TAX_FORM"
    ORPHAN_TAX_FORM = "ORPHAN_TAX_FORM"
    CATASTRAL_MISMATCH = "CATASTRAL_MISMATCH"
    ADDRESS_MISMATCH = "ADDRESS_MISMATCH"
    ADDRESS_FORMAT_DIFFERENCE = "ADDRESS_FORMAT_DIFFERENCE"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    DATE_MISMATCH = "DATE_MISMATCH"
    NOTARY_MISMATCH = "NOTARY_MISMATCH"
    PERCENT_TRANSFERRED_MISMATCH = "PERCENT_TRANSFERRED_MISMATCH"
    SELLER_NIF_MISMATCH = "SELLER_NIF_MISMATCH"
    SELLER_PERCENT_MISMATCH = "SELLER_PERCENT_MISMATCH"
    BUYER_NIF_MISMATCH = "BUYER_NIF_MISMATCH"
    BUYER_PERCENT_MISMATCH = "BUYER_PERCENT_MISMATCH"
    VALUE_MISMATCH = "VALUE_MISMATCH"
    TRANSMITENTE_SUM_ERROR = "TRANSMITENTE_SUM_ERROR"
    MISSING_SELLER = "MISSING_SELLER"
    MISSING_BUYER = "MISSING_BUYER"
    TAX_CALCULATION_ERROR = "TAX_CALCULATION_ERROR"


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
    status: Severity
    matched_forms: List[str] = field(default_factory=list)
    issues: List[Dict[str, Any]] = field(default_factory=list)

    def add_issue(self, issue: Issue):
        self.issues.append({
            "code": issue.code.value,
            "severity": issue.severity.value,
            "field": issue.field,
            "escritura_value": str(issue.escritura_value) if issue.escritura_value is not None else None,
            "tax_form_value": str(issue.tax_form_value) if issue.tax_form_value is not None else None,
            "message": issue.message,
            "form_id": issue.form_id,
        })
        if issue.severity == Severity.ERROR and self.status != Severity.ERROR:
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
    return re.sub(r'\s+', '', ref.upper().strip())


def normalize_address(addr: str) -> str:
    addr = addr.upper().strip()
    addr = re.sub(r'[ÁÀÂÄ]', 'A', addr)
    addr = re.sub(r'[ÉÈÊË]', 'E', addr)
    addr = re.sub(r'[ÍÌÎÏ]', 'I', addr)
    addr = re.sub(r'[ÓÒÔÖ]', 'O', addr)
    addr = re.sub(r'[ÚÙÛÜ]', 'U', addr)
    addr = re.sub(r'Ñ', 'N', addr)
    addr = re.sub(r'\s+', ' ', addr)
    addr = addr.replace('C/', 'CALLE')
    addr = addr.replace('AV.', 'AVENIDA')
    addr = re.sub(r'[,.]', '', addr)
    addr = re.sub(r'\s+', '', addr)
    return addr


def normalize_nif(nif: str) -> str:
    return nif.upper().strip()


def parse_date(date_str: str) -> Optional[datetime]:
    try:
        d, m, y = map(int, date_str.split('-'))
        return datetime(y, m, d)
    except Exception:
        return None


def compare_addresses(addr1: str, addr2: str) -> Tuple[bool, Severity]:
    if normalize_address(addr1) == normalize_address(addr2):
        return True, Severity.OK
    elif addr1.strip().lower() == addr2.strip().lower():
        return False, Severity.WARNING
    return False, Severity.ERROR


def group_by_catastral(items: List[Dict[str, Any]], key_path: str) -> Dict[str, List[Dict[str, Any]]]:
    groups = {}
    for item in items:
        keys = key_path.split('.')
        val = item
        for k in keys:
            val = val.get(k, '')
        ref = normalize_catastral_ref(str(val))
        if ref not in groups:
            groups[ref] = []
        groups[ref].append(item)
    return groups


def compare_property_identity(prop: Dict, form: Dict, report: PropertyComparisonReport):
    prop_ref = normalize_catastral_ref(prop['ref_catastral'])
    form_ref = normalize_catastral_ref(form['property']['ref_catastral'])

    if prop_ref != form_ref:
        report.add_issue(Issue(
            code=IssueCode.CATASTRAL_MISMATCH,
            severity=Severity.ERROR,
            field="ref_catastral",
            escritura_value=prop['ref_catastral'],
            tax_form_value=form['property']['ref_catastral'],
            message="Catastral reference mismatch",
            form_id=form.get('form_id'),
        ))

    addr_match, addr_severity = compare_addresses(
        prop.get('address', ''),
        form['property'].get('address', '')
    )
    if not addr_match:
        report.add_issue(Issue(
            code=IssueCode.ADDRESS_FORMAT_DIFFERENCE if addr_severity == Severity.WARNING else IssueCode.ADDRESS_MISMATCH,
            severity=addr_severity,
            field="address",
            escritura_value=prop.get('address'),
            tax_form_value=form['property'].get('address'),
            message="Address text differs" if addr_severity == Severity.WARNING else "Address mismatch",
            form_id=form.get('form_id'),
        ))

    prop_type = prop['type'].lower() if isinstance(prop['type'], str) else prop['type'].value.lower()
    form_nature = form['nature'].lower() if isinstance(form['nature'], str) else form['nature'].value.lower()

    type_match = (
        (prop_type == 'urbana' and 'urbanos' in form_nature) or
        (prop_type in ['rustica', 'rústica'] and 'rusticos' in form_nature)
    )
    if not type_match:
        report.add_issue(Issue(
            code=IssueCode.TYPE_MISMATCH,
            severity=Severity.ERROR,
            field="type",
            escritura_value=prop_type,
            tax_form_value=form_nature,
            message="Property type does not match form nature",
            form_id=form.get('form_id'),
        ))


def compare_transaction_data(escritura: Dict, form: Dict, report: PropertyComparisonReport):
    escr_date = parse_date(escritura['date_of_sale'])
    form_date = parse_date(form['operation']['fecha_devengo'])

    if escr_date and form_date and escr_date != form_date:
        report.add_issue(Issue(
            code=IssueCode.DATE_MISMATCH,
            severity=Severity.ERROR,
            field="date",
            escritura_value=escritura['date_of_sale'],
            tax_form_value=form['operation']['fecha_devengo'],
            message="Sale date does not match fecha_devengo",
            form_id=form.get('form_id'),
        ))

    escr_notary = escritura['notary']['name'].upper().strip()
    if 'notary' in form:
        form_notary = form['notary'].get('name', '').upper().strip()
        if escr_notary != form_notary and form_notary:
            report.add_issue(Issue(
                code=IssueCode.NOTARY_MISMATCH,
                severity=Severity.WARNING,
                field="notary",
                escritura_value=escr_notary,
                tax_form_value=form_notary,
                message="Notary name differs",
                form_id=form.get('form_id'),
            ))


def compare_parties(escritura: Dict, prop: Dict, forms: List[Dict], report: PropertyComparisonReport):
    seller_nifs = {normalize_nif(s['nif']) for s in escritura['sellers']}
    buyer_nifs = {normalize_nif(b['nif']) for b in escritura['buyers']}

    for form in forms:
        form_id = form.get('form_id')

        transmitente_nifs = {normalize_nif(t['nif']) for t in form['transmitentes']}
        missing_sellers = seller_nifs - transmitente_nifs
        if missing_sellers:
            report.add_issue(Issue(
                code=IssueCode.MISSING_SELLER,
                severity=Severity.ERROR,
                field="transmitentes",
                escritura_value=list(seller_nifs),
                tax_form_value=list(transmitente_nifs),
                message=f"Sellers missing in tax form: {missing_sellers}",
                form_id=form_id,
            ))

        total_transmitente_pct = sum(Decimal(str(t['transmission_coefficient'])) for t in form['transmitentes'])
        if abs(total_transmitente_pct - Decimal('100')) > Decimal('0.01'):
            report.add_issue(Issue(
                code=IssueCode.TRANSMITENTE_SUM_ERROR,
                severity=Severity.ERROR,
                field="transmitentes.transmission_coefficient",
                escritura_value=100,
                tax_form_value=float(total_transmitente_pct),
                message=f"Transmitente percentages sum to {total_transmitente_pct}%, expected 100%",
                form_id=form_id,
            ))

        sujeto_nif = normalize_nif(form['sujeto_pasivo']['nif'])
        if sujeto_nif not in buyer_nifs:
            report.add_issue(Issue(
                code=IssueCode.BUYER_NIF_MISMATCH,
                severity=Severity.ERROR,
                field="sujeto_pasivo.nif",
                escritura_value=list(buyer_nifs),
                tax_form_value=sujeto_nif,
                message="Buyer NIF in tax form not found in escritura",
                form_id=form_id,
            ))


def compare_financial_amounts(prop: Dict, forms: List[Dict], report: PropertyComparisonReport, tolerance: Decimal = Decimal('0.01')):
    prop_value = Decimal(str(prop['declared_value_escritura']))

    total_valor_declarado = sum(
        Decimal(str(f['liquidation_data']['valor_declarado'])) for f in forms
    )

    if len(forms) == 1:
        form = forms[0]
        form_value = Decimal(str(form['liquidation_data']['valor_declarado']))
        percent_transferred = Decimal(str(form['property'].get('percent_transferred', 100)))
        expected_value = prop_value * percent_transferred / Decimal('100')

        if abs(form_value - expected_value) > tolerance:
            report.add_issue(Issue(
                code=IssueCode.VALUE_MISMATCH,
                severity=Severity.ERROR,
                field="liquidation_data.valor_declarado",
                escritura_value=float(expected_value),
                tax_form_value=float(form_value),
                message=f"Declared value in tax form ({form_value}) does not match expected value ({expected_value})",
                form_id=form.get('form_id'),
            ))
    else:
        if abs(total_valor_declarado - prop_value) > tolerance:
            report.add_issue(Issue(
                code=IssueCode.VALUE_MISMATCH,
                severity=Severity.ERROR,
                field="liquidation_data.valor_declarado",
                escritura_value=float(prop_value),
                tax_form_value=float(total_valor_declarado),
                message=f"Sum of valores_declarados ({total_valor_declarado}) does not match property value ({prop_value})",
            ))

    for form in forms:
        liq = form['liquidation_data']
        form_id = form.get('form_id')

        base_liq = Decimal(str(liq['base_liquidable']))
        tipo = Decimal(str(liq['tipo']))
        cuota = Decimal(str(liq['cuota']))
        expected_cuota = base_liq * tipo / Decimal('100')

        if abs(cuota - expected_cuota) > tolerance:
            report.add_issue(Issue(
                code=IssueCode.TAX_CALCULATION_ERROR,
                severity=Severity.ERROR,
                field="liquidation_data.cuota",
                escritura_value=float(expected_cuota),
                tax_form_value=float(cuota),
                message=f"Tax cuota calculation error: expected {expected_cuota}, got {cuota}",
                form_id=form_id,
            ))


def compare_escritura_with_tax_forms(data: Dict[str, List[Dict]]) -> List[Dict[str, Any]]:
    escrituras = data['escrituras']
    tax_forms = data['tax_forms']
    reports = []

    for i, form in enumerate(tax_forms):
        if 'form_id' not in form:
            form['form_id'] = f"form_{i}"

    for i, escritura in enumerate(escrituras):
        if 'id' not in escritura:
            escritura['id'] = f"escritura_{i}"

    tax_by_catastral = group_by_catastral(tax_forms, 'property.ref_catastral')
    matched_form_ids = set()

    for escritura in escrituras:
        for prop in escritura['properties']:
            prop_id = f"{escritura['id']}:{prop['id']}"
            ref = normalize_catastral_ref(prop['ref_catastral'])

            report = PropertyComparisonReport(
                property_id=prop_id,
                ref_catastral=prop['ref_catastral'],
                status=Severity.OK,
            )

            matching_forms = tax_by_catastral.get(ref, [])

            if not matching_forms:
                report.add_issue(Issue(
                    code=IssueCode.MISSING_TAX_FORM,
                    severity=Severity.ERROR,
                    field="tax_forms",
                    escritura_value=ref,
                    tax_form_value=None,
                    message=f"No tax forms found for property {ref}",
                ))
                reports.append(report.to_dict())
                continue

            report.matched_forms = [f.get('form_id') for f in matching_forms]
            matched_form_ids.update(report.matched_forms)

            for form in matching_forms:
                compare_property_identity(prop, form, report)
                compare_transaction_data(escritura, form, report)

            compare_parties(escritura, prop, matching_forms, report)
            compare_financial_amounts(prop, matching_forms, report)

            reports.append(report.to_dict())

    all_form_ids = {f['form_id'] for f in tax_forms}
    orphan_form_ids = all_form_ids - matched_form_ids

    for orphan_id in orphan_form_ids:
        orphan_form = next(f for f in tax_forms if f['form_id'] == orphan_id)
        ref = orphan_form['property']['ref_catastral']

        report = PropertyComparisonReport(
            property_id=f"orphan:{orphan_id}",
            ref_catastral=ref,
            status=Severity.ERROR,
            matched_forms=[orphan_id],
        )
        report.add_issue(Issue(
            code=IssueCode.ORPHAN_TAX_FORM,
            severity=Severity.ERROR,
            field="property.ref_catastral",
            escritura_value=None,
            tax_form_value=ref,
            message=f"Tax form {orphan_id} references property {ref} not found in any escritura",
            form_id=orphan_id,
        ))
        reports.append(report.to_dict())

    return reports
