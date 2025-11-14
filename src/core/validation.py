from datetime import date
from typing import List, Optional
from decimal import Decimal
from enum import Enum
import re
from pydantic import BaseModel, Field, field_validator, model_validator
from .spanish_id import validate_spanish_id


class PropertyType(str, Enum):
    URBANA = "urbana"
    RUSTICA = "rústica"

class FormType(str, Enum):
    FORM_600U = "600U"
    FORM_600R = "600R"

class NatureType(str, Enum):
    URBANOS = "bienes_inmuebles_urbanos"
    RUSTICOS = "bienes_inmuebles_rusticos"

class AssetType(str, Enum):
    VIVIENDA = "Vivienda"
    RUSTICA = "Rustica"


class Person(BaseModel):
    role: str = Field(..., min_length=1)
    full_name: str = Field(..., min_length=1)
    nif: str = Field(..., min_length=8, max_length=9)
    marital_regime: Optional[str] = None

    @field_validator('nif')
    @classmethod
    def validate_nif(cls, v: str) -> str:
        v = v.upper().strip()
        if not validate_spanish_id(v):
            raise ValueError(f'Invalid Spanish ID (DNI/NIE/CIF): {v}')
        return v

    @field_validator('full_name')
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        v = v.strip()
        if v.count(' ') < 1:
            raise ValueError(f'Full name needs first and last: {v}')
        return v


class Notary(BaseModel):
    name: str = Field(..., min_length=1)
    college: str

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if v.count(' ') < 1:
            raise ValueError(f'Notary name needs at least two parts: {v}')
        return v


class Property(BaseModel):
    id: str
    type: PropertyType
    address: str = Field(..., min_length=5)
    ref_catastral: str = Field(..., min_length=14, max_length=20)
    declared_value_escritura: Decimal = Field(..., gt=0)
    area_usable: Optional[Decimal] = Field(None, ge=0)
    area_built: Optional[Decimal] = Field(None, ge=0)
    municipality: Optional[str] = None
    province: Optional[str] = None

    @field_validator('ref_catastral')
    @classmethod
    def validate_catastral_ref(cls, v: str) -> str:
        v = v.upper().strip()
        if not re.match(r'^[A-Z0-9]{14,20}$', v):
            raise ValueError(f'Invalid catastral ref: {v}')
        return v

    @field_validator('address')
    @classmethod
    def validate_address(cls, v: str) -> str:
        v = v.strip()
        if not any(kw in v.upper() for kw in ['C/', 'CALLE', 'AVENIDA', 'AV.', 'PLAZA']):
            raise ValueError(f'Address missing street type: {v}')
        return v


class PriceBreakdown(BaseModel):
    property_id: str
    seller_nif: str
    amount: Decimal = Field(..., gt=0)


class ExpensesClause(BaseModel):
    who_pays_taxes: str
    incremento_valor_terrenos_urbanos: str
    other_expenses: Optional[str] = None


class Escritura(BaseModel):
    notary: Notary
    date_of_sale: str
    sellers: List[Person] = Field(..., min_length=1)
    buyers: List[Person] = Field(..., min_length=1)
    properties: List[Property] = Field(..., min_length=1)
    price_breakdown: List[PriceBreakdown]
    expenses_clause: ExpensesClause

    @field_validator('date_of_sale')
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        if not re.match(r'^\d{2}-\d{2}-\d{4}$', v):
            raise ValueError(f'Invalid date: {v}. Use DD-MM-YYYY')
        try:
            d, m, y = map(int, v.split('-'))
            date(y, m, d)
        except ValueError as e:
            raise ValueError(f'Invalid date: {v}. {str(e)}')
        return v

    @model_validator(mode='after')
    def validate_price_breakdown_totals(self) -> 'Escritura':
        for prop in self.properties:
            total = sum(pb.amount for pb in self.price_breakdown if pb.property_id == prop.id)
            if abs(total - prop.declared_value_escritura) > Decimal('0.01'):
                raise ValueError(
                    f'Property {prop.id}: breakdown {total} != declared {prop.declared_value_escritura}'
                )
        return self

    @model_validator(mode='after')
    def validate_sellers_in_breakdown(self) -> 'Escritura':
        seller_nifs = {s.nif for s in self.sellers}
        breakdown_nifs = {pb.seller_nif for pb in self.price_breakdown}
        invalid = breakdown_nifs - seller_nifs
        if invalid:
            raise ValueError(f'Unknown sellers in breakdown: {invalid}')
        return self


class Transmitente(BaseModel):
    nif: str = Field(..., min_length=8, max_length=9)
    name: str = Field(..., min_length=1)
    transmission_coefficient: Decimal = Field(..., ge=0, le=100)

    @field_validator('nif')
    @classmethod
    def validate_nif(cls, v: str) -> str:
        v = v.upper().strip()
        if not validate_spanish_id(v):
            raise ValueError(f'Invalid Spanish ID (DNI/NIE/CIF): {v}')
        return v


class Operation(BaseModel):
    concepto: str
    fecha_devengo: str

    @field_validator('fecha_devengo')
    @classmethod
    def validate_date(cls, v: str) -> str:
        if not re.match(r'^\d{2}-\d{2}-\d{4}$', v):
            raise ValueError(f'Invalid date: {v}. Use DD-MM-YYYY')
        try:
            d, m, y = map(int, v.split('-'))
            date(y, m, d)
        except ValueError as e:
            raise ValueError(f'Invalid date: {v}. {str(e)}')
        return v


class PropertyTaxForm(BaseModel):
    ref_catastral: str = Field(..., min_length=14, max_length=20)
    address: str
    type_of_asset: AssetType
    percent_transferred: Decimal = Field(..., ge=0, le=100)

    @field_validator('ref_catastral')
    @classmethod
    def validate_catastral_ref(cls, v: str) -> str:
        v = v.upper().strip()
        if not re.match(r'^[A-Z0-9]{14,20}$', v):
            raise ValueError(f'Invalid catastral ref: {v}')
        return v


class TechnicalData(BaseModel):
    destinada_vivienda_habitual: Optional[bool] = None
    segunda_vivienda_mismo_municipio: Optional[bool] = None
    constructed_surface: Optional[Decimal] = Field(None, ge=0)
    other_details: Optional[str] = None


class LiquidationData(BaseModel):
    valor_declarado: Decimal = Field(..., ge=0)
    coef_adquisicion: Optional[Decimal] = Field(None, ge=0, le=1)
    base_imponible: Decimal = Field(..., ge=0)
    reduccion: Decimal = Field(default=Decimal('0'), ge=0)
    base_liquidable: Decimal = Field(..., ge=0)
    tipo: Decimal = Field(..., ge=0, le=100)
    cuota: Decimal = Field(..., ge=0)
    bonificacion: Decimal = Field(default=Decimal('0'), ge=0, le=100)
    a_ingresar: Decimal = Field(..., ge=0)
    intereses_mora: Decimal = Field(default=Decimal('0'), ge=0)
    deuda_tributaria: Decimal = Field(..., ge=0)

    @model_validator(mode='after')
    def validate_calculations(self) -> 'LiquidationData':
        eps = Decimal('0.01')

        exp_base_liq = self.base_imponible - self.reduccion
        if abs(self.base_liquidable - exp_base_liq) > eps:
            raise ValueError(f'base_liquidable {self.base_liquidable} != base_imponible {self.base_imponible} - reduccion {self.reduccion}')

        exp_cuota = self.base_liquidable * self.tipo / Decimal('100')
        if abs(self.cuota - exp_cuota) > eps:
            raise ValueError(f'cuota {self.cuota} != base_liquidable {self.base_liquidable} × tipo {self.tipo}%')
        exp_a_ing = self.cuota - (self.cuota * self.bonificacion / Decimal('100'))
        if abs(self.a_ingresar - exp_a_ing) > eps:
            raise ValueError(f'a_ingresar {self.a_ingresar} != cuota {self.cuota} - bonificacion {self.bonificacion}%')

        exp_deuda = self.a_ingresar + self.intereses_mora
        if abs(self.deuda_tributaria - exp_deuda) > eps:
            raise ValueError(f'deuda_tributaria {self.deuda_tributaria} != a_ingresar {self.a_ingresar} + intereses_mora {self.intereses_mora}')

        return self


class Modelo600(BaseModel):
    form_type: FormType
    nature: NatureType
    sujeto_pasivo: Person
    transmitentes: List[Transmitente] = Field(..., min_length=1)
    operation: Operation
    property: PropertyTaxForm
    technical_data: Optional[TechnicalData] = None
    liquidation_data: LiquidationData

    @model_validator(mode='after')
    def validate_form_type_consistency(self) -> 'Modelo600':
        if self.form_type == FormType.FORM_600U:
            if self.nature != NatureType.URBANOS:
                raise ValueError(f'600U requires urbanos, got {self.nature}')
            if self.property.type_of_asset != AssetType.VIVIENDA:
                raise ValueError(f'600U requires Vivienda, got {self.property.type_of_asset}')
        elif self.form_type == FormType.FORM_600R:
            if self.nature != NatureType.RUSTICOS:
                raise ValueError(f'600R requires rusticos, got {self.nature}')
            if self.property.type_of_asset != AssetType.RUSTICA:
                raise ValueError(f'600R requires Rustica, got {self.property.type_of_asset}')
        return self

    @model_validator(mode='after')
    def validate_transmission_coefficients(self) -> 'Modelo600':
        total = sum(t.transmission_coefficient for t in self.transmitentes)
        if abs(total - Decimal('100')) > Decimal('0.01'):
            raise ValueError(f'Transmission coefficients sum to {total}%, need 100%')
        return self


rules = {
    "name": lambda x: x.count(" ") >= 1,
    "spanish_id": validate_spanish_id,
    "date_format": lambda x: bool(re.match(r'^\d{2}-\d{2}-\d{4}$', x)),
    "catastral_ref": lambda x: bool(re.match(r'^[A-Z0-9]{14,20}$', x.upper())),
}


def validate_data(x: dict) -> BaseModel:
    if 'notary' in x and 'sellers' in x and 'buyers' in x:
        return Escritura.model_validate(x)
    elif 'form_type' in x and 'sujeto_pasivo' in x and 'liquidation_data' in x:
        return Modelo600.model_validate(x)
    raise ValueError("Cannot determine type: need Escritura fields (notary/sellers/buyers) or Modelo600 fields (form_type/sujeto_pasivo/liquidation_data)")
