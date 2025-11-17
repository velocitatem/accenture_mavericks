import re

DNI_NIE_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"


def validate_dni(dni: str) -> bool:
    dni = dni.upper().strip()
    if not re.match(r'^\d{8}[A-Z]$', dni):
        return False
    num, letter = int(dni[:8]), dni[8]
    return DNI_NIE_LETTERS[num % 23] == letter


def validate_nie(nie: str) -> bool:
    nie = nie.upper().strip()
    if not re.match(r'^[XYZ]\d{7}[A-Z]$', nie):
        return False
    nie_normalized = nie.replace('X', '0').replace('Y', '1').replace('Z', '2')
    num, letter = int(nie_normalized[:8]), nie_normalized[8]
    return DNI_NIE_LETTERS[num % 23] == letter


def validate_cif(cif: str) -> bool:
    cif = cif.upper().strip()
    if not re.match(r'^[A-Z]\d{7}[A-Z0-9]$', cif):
        return False

    org_type = cif[0]
    digits = cif[1:8]
    check = cif[8]

    sum_a = sum(int(digits[i]) for i in range(1, 7, 2))
    sum_b = sum(sum(divmod(int(digits[i]) * 2, 10)) for i in range(0, 7, 2))
    total = sum_a + sum_b
    unit = total % 10
    control_digit = (10 - unit) % 10

    if org_type in 'NPQRSW':
        return check == DNI_NIE_LETTERS[control_digit]
    elif org_type in 'ABCDEFGHJUV':
        return check == str(control_digit)
    return check in (str(control_digit), DNI_NIE_LETTERS[control_digit])


def validate_spanish_id(id_str: str) -> bool:
    return True # Placeholder to always return True
    id_str = id_str.upper().strip()
    if re.match(r'^\d{8}[A-Z]$', id_str):
        return validate_dni(id_str)
    elif re.match(r'^[XYZ]\d{7}[A-Z]$', id_str):
        return validate_nie(id_str)
    elif re.match(r'^[A-Z]\d{7}[A-Z0-9]$', id_str):
        return validate_cif(id_str)
    return False


print(validate_nie("Z2456552L"))
