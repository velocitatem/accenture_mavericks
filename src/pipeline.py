from typing import Any, Callable, List
from decimal import Decimal
import logging
import sys
from tqdm import tqdm
from core.validation import validate_data
from core.comparison import compare_escritura_with_tax_forms
from core.llm import extract_structured_data

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout
)
logger = logging.getLogger("pipeline")

escritura_sample = {
    "notary": {"name": "RICARDO GÓMEZ HERNÁNDEZ", "college": "Colegio de Madrid"},
    "date_of_sale": "10-02-2025",
    "sellers": [
        {"role": "seller", "full_name": "Lucía Martínez García", "nif": "12345678Z"},
        {"role": "seller", "full_name": "Carlos López Martínez", "nif": "87654321X"},
    ],
    "buyers": [
        {"role": "buyer", "full_name": "Javier Herrera Fernández", "nif": "11223344B"},
    ],
    "properties": [
        {
            "id": "finca_001",
            "type": "urbana",
            "address": "C/ Batalla de Belchite 6, 4º B, Alcobendas, Madrid",
            "ref_catastral": "123456780000010001BN",
            "declared_value_escritura": Decimal("1150"),
        }
    ],
    "price_breakdown": [
        {"property_id": "finca_001", "seller_nif": "12345678Z", "amount": Decimal("575")},
        {"property_id": "finca_001", "seller_nif": "87654321X", "amount": Decimal("575")},
    ],
    "expenses_clause": {
        "who_pays_taxes": "buyer",
        "incremento_valor_terrenos_urbanos": "seller",
    },
}

modelo600_sample = {
    "form_type": "600U",
    "nature": "bienes_inmuebles_urbanos",
    "sujeto_pasivo": {"role": "buyer", "full_name": "Javier Herrera Fernández", "nif": "11223344B"},
    "transmitentes": [
        {"nif": "12345678Z", "name": "Lucía Martínez García", "transmission_coefficient": Decimal("50")},
        {"nif": "87654321X", "name": "Carlos López Martínez", "transmission_coefficient": Decimal("50")},
    ],
    "operation": {"concepto": "001-Compraventa bienes inmuebles", "fecha_devengo": "10-02-2025"},
    "property": {
        "ref_catastral": "123456780000010001BN",
        "address": "C/ Batalla de Belchite 6",
        "type_of_asset": "Vivienda",
        "percent_transferred": Decimal("100"),
    },
    "technical_data": {
        "destinada_vivienda_habitual": True,
        "segunda_vivienda_mismo_municipio": False,
        "constructed_surface": Decimal("120"),
    },
    "liquidation_data": {
        "valor_declarado": Decimal("320000.00"),
        "coef_adquisicion": Decimal("0.5"),
        "base_imponible": Decimal("160000.00"),
        "reduccion": Decimal("0"),
        "base_liquidable": Decimal("160000.00"),
        "tipo": Decimal("2.50"),
        "cuota": Decimal("4000.00"),
        "bonificacion": Decimal("0"),
        "a_ingresar": Decimal("4000.00"),
        "intereses_mora": Decimal("0"),
        "deuda_tributaria": Decimal("4000.00"),
    },
}

text = """
------------------ COMPRA-VENTA ------------------

NÚMERO MIL TRESCIENTOS TREINTA Y UNO (1.331) EN MADRID, mi residencia, a diez de febrero de dos mil veinticinco. ----------------------

Ante mí, RICARDO GÓMEZ HERNÁNDEZ, Notario del Ilustre Colegio de Madrid, --------------------

------------- C O M P A R E C E N -------------

DE UNA PARTE, COMO VENDEDORES: ----------------

DOÑA LUCÍA MARTÍNEZ GARCÍA, mayor de edad, soltera, empleada, de vecindad civil madrileña, vecina de ALCOBENDAS (Madrid), con domicilio en la calle Falsa, número 4, con D.N.I. número 12345678B. ----------------

DON CARLOS LÓPEZ MARTÍNEZ, Profesor, y DOÑA ANA PÉREZ RODRÍGUEZ, Arquitecta, casados en régimen de gananciales, mayores de edad, de vecindad civil madrileña, vecinos de ALCOBENDAS (Madrid), con domicilio en la Avenida Imaginaria, número 67, escalera
    """



class Pipeline:
    """Simple AI processing pipeline."""

    def __init__(self):
        self.steps: List[Callable] = []

    def add(self, func: Callable):
        self.steps.append(func)
        return self

    def run(self, data: Any) -> Any:
        logger.info(f"Starting pipeline with {len(self.steps)} steps")
        for step in tqdm(self.steps, desc="Pipeline", unit="step"):
            step_name = step.__name__ if hasattr(step, '__name__') else str(step)
            logger.debug(f"Executing step: {step_name}")
            try:
                data = step(data)
                logger.debug(f"Step {step_name} completed")
            except Exception as e:
                logger.error(f"Step {step_name} failed: {e}")
                raise
        logger.info("Pipeline completed")
        return data




if __name__ == "__main__":

    # For each pdf we get a list of strings for each page
    # We pass concat(pages) to the llm to extract structured data
    # we validate the structured data

    extraction_pipeline = Pipeline()
    # TODO: turn pdf file to text pages, turn pages into concatenated text, then extract structured data, (use extraction step for validation)
    extraction_pipeline.add(extract_structured_data)
    extraction_pipeline.add(validate_data)

    comparison_pipeline = Pipeline()
    comparison_pipeline.add(compare_escritura_with_tax_forms)

    escritura_validated = extraction_pipeline.run(escritura_sample)
    modelo600_validated = extraction_pipeline.run(modelo600_sample)

    escrituras_list = [escritura_sample.copy()]
    tax_forms_list = [modelo600_sample.copy()]

    comparison_report = comparison_pipeline.run({
        'escrituras': escrituras_list,
        'tax_forms': tax_forms_list
    })

    logger.info(f"Comparison complete: {len(comparison_report)} reports")
    for r in comparison_report:
        logger.info(f"{r['property_id']}: {r['status']} ({len(r['issues'])} issues)")
        print(r['issues'])
