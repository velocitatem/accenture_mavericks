from datetime import date
from typing import List, Optional, Union, Any, Dict
from decimal import Decimal
from enum import Enum
import re
from pydantic import BaseModel, Field, field_validator, model_validator
from .spanish_id import validate_spanish_id


# --- Enums ---

class PropertyType(str, Enum):
    URBANA = "urbana"
    RUSTICA = "rústica"
    VIVIENDA = "vivienda"
    FINCA = "finca"
    OTHER = "other"

class FormType(str, Enum):
    FORM_600U = "600U"
    FORM_600R = "600R"

# --- Common Helpers ---

def clean_decimal(v: Any) -> Optional[Decimal]:
    if v is None:
        return None
    if isinstance(v, (int, float, Decimal)):
        return Decimal(str(v))
    if isinstance(v, str):
        # Remove currency symbols and text
        v = re.sub(r'[€$£¥]|\s*EUR\s*|\s*USD\s*', '', v.strip())
        # Remove thousands separators (assuming comma is decimal separator in some contexts, 
        # but standardizing on dot for decimal. If comma is used as decimal separator, replace it)
        # In Spanish format 1.000,00 -> remove . replace , with .
        # In English format 1,000.00 -> remove ,
        # Heuristic: if ',' is present and '.' is not, or ',' is after '.', treat as decimal separator
        if ',' in v and '.' not in v:
             v = v.replace(',', '.')
        elif ',' in v and '.' in v:
             # ambiguous, assume standard english if dot is last
             v = v.replace(',', '')
        
        return Decimal(v)
    return v

def validate_date_format(v: str) -> str:
    if not v: return v
    v = v.strip()
    # Try to parse various date formats and convert to DD-MM-YYYY
    if re.match(r'^\d{4}-\d{2}-\d{2}', v):
        y, m, d = v[:10].split('-')
        v = f"{d}-{m}-{y}"
    elif '/' in v:
        v = v.replace('/', '-')
    
    if not re.match(r'^\d{2}-\d{2}-\d{4}$', v):
        # Allow returning as is if it fails, or raise error? 
        # Ground truth has "10-02-2025", so we enforce it.
        raise ValueError(f'Invalid date: {v}. Use DD-MM-YYYY')
    return v

# --- Shared Models ---

class Person(BaseModel):
    role: str = Field(..., description="seller or buyer")
    full_name: str
    # NIF fields vary by role in ground truth: seller_nif vs buyer_nif vs nif
    # We will use aliases or optional fields to accommodate both, or specific subclasses
    nif: Optional[str] = None 
    seller_nif: Optional[str] = None
    buyer_nif: Optional[str] = None
    
    civil_status: Optional[str] = None
    marital_regime: Optional[str] = None
    spouse_nif: Optional[str] = None
    # marital_regime already defined above

    @model_validator(mode='after')
    def consolidate_nif(self) -> 'Person':
        # Ensure at least one NIF is present and populate 'nif' for internal logic if needed
        if not self.nif:
            if self.seller_nif: self.nif = self.seller_nif
            elif self.buyer_nif: self.nif = self.buyer_nif
        return self

class Notary(BaseModel):
    name: str
    nif: Optional[str] = None
    college: Optional[str] = None

class SaleBreakdownItem(BaseModel):
    property_id: str
    buyer_nif: str
    seller_nif: str
    percentage_sold: Union[Decimal, str]
    amount: Optional[Decimal] = None # In escritura ground truth it's not explicitly in breakdown list but implied? 
    # Wait, escritura ground truth has "percentage_sold" in sale_breakdown? 
    # Actually, checking file content: 
    # Escritura ground truth: "sale_breakdown": [{"property_id":..., "percentage_sold": "10.00"}]
    # Original code had "amount". Ground truth has "percentage_sold".
    # I will support both for flexibility, but ground truth uses percentage.

class ExpensesClause(BaseModel):
    who_pays_taxes: str
    plusvalia: Optional[str] = None
    incremento_valor_terrenos_urbanos: Optional[str] = None # Alias for plusvalia

class DocumentInfo(BaseModel):
    page: str
    model: str
    date_of_sale: str

# --- Property Models ---

class PropertyBase(BaseModel):
    id: Optional[str] = None
    property_type: Optional[str] = None # 600U / 600R
    type: Optional[str] = None # vivienda, finca, etc.
    address: Optional[str] = None
    ref_catastral: str
    declared_value: Union[Decimal, str]
    surface_area: Optional[Union[Decimal, str]] = None
    registry_info: Optional[str] = None # Registro: [número y localidad] — Tomo: [tomo] — Libro: [libro] — Folio: [folio] — Finca: [número de finca]
    purchase_year: Optional[str] = None # DD-MM-YYYY of previous purchase

    # Escritura specific - using Dict instead of custom model to allow dynamic keys
    ownership_distribution: Optional[Dict[str, float]] = None  # Dict[NIF, percentage]
    adquisition_info: Optional[Dict[str, str]] = None  # Dict[NIF, date]

    # Autoliquidacion specific
    main_residence: Optional[bool] = None

    model_config = {"extra": "forbid"}

    @field_validator('declared_value', mode='before')
    @classmethod
    def validate_value(cls, v):
        return str(v) # Keep as string to match ground truth or Decimal? Ground truth has strings "1150"

# --- Top Level Models ---

class Escritura(BaseModel):
    notary: Notary
    document_number: str
    date_of_sale: str
    sellers: List[Person]
    buyers: List[Person]
    properties: List[PropertyBase]
    sale_breakdown: List[SaleBreakdownItem]
    expenses_clause: ExpensesClause

    @field_validator('date_of_sale')
    @classmethod
    def val_date(cls, v): return validate_date_format(v)

class Modelo600(BaseModel):
    notary: Notary
    document_number: Optional[str] = None
    date_of_sale: str
    document_info: Optional[List[DocumentInfo]] = None
    sellers: List[Person]
    buyers: List[Person]
    properties: List[PropertyBase]
    sale_breakdown: Optional[List[SaleBreakdownItem]] = None
    expenses_clause: Optional[ExpensesClause] = None
    
    # Legacy/Optional fields for comparison if we want to add them back later
    # liquidation_data: Optional[LiquidationData] = None 

    @field_validator('date_of_sale')
    @classmethod
    def val_date(cls, v): return validate_date_format(v)

def validate_data(x: dict | BaseModel) -> BaseModel:
    if isinstance(x, Escritura) or isinstance(x, Modelo600):
        return x
    
    if isinstance(x, dict):
        # Heuristic to distinguish
        if 'document_info' in x:
            return Modelo600.model_validate(x)
        if 'notary' in x and 'sellers' in x:
            return Escritura.model_validate(x)
            
    raise ValueError("Cannot determine type")

if __name__ == "__main__":
    import json
    from pathlib import Path
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    project_root = Path(__file__).parent.parent.parent
    ground_truths_dir = project_root / "ground-truths"

    # Verify Modelo600
    try:
        with open(ground_truths_dir / "autoliquidacion_caso_real_completo.json", "r") as f:
            data_600 = json.load(f)
        Modelo600.model_validate(data_600)
        logger.info("Modelo600 validation passed")
    except Exception as e:
        logger.error(f"Modelo600 validation failed: {e}")

    # Verify Escritura
    try:
        with open(ground_truths_dir / "escritura_caso_real_completo.json", "r") as f:
            data_escritura = json.load(f)
        Escritura.model_validate(data_escritura)
        logger.info("Escritura validation passed")
    except Exception as e:
        logger.error(f"Escritura validation failed: {e}")

