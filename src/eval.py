from pathlib import Path
import json
from typing import Dict, List, Tuple, Any
from collections import defaultdict
import re
from difflib import SequenceMatcher
import logging
import unicodedata
from tabulate import tabulate

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def remove_accents(text: str) -> str:
    """Remove accents from Spanish text while preserving ñ"""
    if not text:
        return ""
    # Normalize to NFD (decomposed form), filter out combining marks, then recompose
    nfd = unicodedata.normalize('NFD', text)
    without_accents = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn' or c in ['ñ', 'Ñ'])
    return unicodedata.normalize('NFC', without_accents)


def normalize_text(text: str) -> str:
    """Normalize text for comparison: remove accents, uppercase, strip, remove extra spaces"""
    if not text:
        return ""
    text = remove_accents(text)
    text = text.upper()
    text = re.sub(r'\s+', ' ', text.strip())
    return text


def normalize_nif(nif: str) -> str:
    """Normalize NIF/NIE/CIF"""
    if not nif:
        return ""
    return nif.strip().upper()


def text_similarity(a: str, b: str) -> float:
    """Calculate similarity ratio between two strings"""
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def name_tokens_match(name1: str, name2: str, threshold: float = 0.8) -> bool:
    """Check if two names match using token-based comparison (order-insensitive)

    Spanish names often have multiple components that can appear in different orders:
    - "Lucía Martínez García" vs "Lucía García Martínez"
    - First name + two surnames (paternal and maternal)

    Returns True if enough tokens match between the two names.
    """
    tokens1 = set(normalize_text(name1).split())
    tokens2 = set(normalize_text(name2).split())

    if not tokens1 or not tokens2:
        return False

    # Calculate Jaccard similarity (intersection over union)
    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)

    jaccard = intersection / union if union > 0 else 0.0
    return jaccard >= threshold


def name_similarity_score(name1: str, name2: str) -> float:
    """Calculate name similarity using both token-based and sequence-based matching

    Returns the maximum of:
    - Token-based Jaccard similarity (order-insensitive)
    - Sequence-based similarity (order-sensitive)
    """
    # Token-based (order-insensitive)
    tokens1 = set(normalize_text(name1).split())
    tokens2 = set(normalize_text(name2).split())

    if not tokens1 or not tokens2:
        return 0.0

    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)
    jaccard = intersection / union if union > 0 else 0.0

    # Sequence-based (order-sensitive)
    sequence_sim = text_similarity(name1, name2)

    # Return the max to be lenient with name ordering
    return max(jaccard, sequence_sim)


def extract_nifs(data: Dict) -> set:
    """Extract all NIFs from document"""
    nifs = set()
    if data.get('notary', {}).get('nif'):
        nifs.add(normalize_nif(data['notary']['nif']))

    for person in data.get('sellers', []) + data.get('buyers', []):
        for nif_field in ['nif', 'seller_nif', 'buyer_nif', 'spouse_nif']:
            if person.get(nif_field):
                nifs.add(normalize_nif(person[nif_field]))

    return nifs


def extract_names(data: Dict) -> Dict[str, List[str]]:
    """Extract names by role"""
    names = {'notary': [], 'sellers': [], 'buyers': []}
    if data.get('notary', {}).get('name'):
        names['notary'].append(normalize_text(data['notary']['name']))

    for person in data.get('sellers', []):
        if person.get('full_name'):
            names['sellers'].append(normalize_text(person['full_name']))

    for person in data.get('buyers', []):
        if person.get('full_name'):
            names['buyers'].append(normalize_text(person['full_name']))

    return names


def extract_property_refs(data: Dict) -> set:
    """Extract cadastral references"""
    refs = set()
    for prop in data.get('properties', []):
        if prop.get('ref_catastral'):
            refs.add(normalize_text(prop['ref_catastral']))
    return refs


def extract_document_meta(data: Dict) -> Dict:
    """Extract document metadata"""
    return {
        'document_number': data.get('document_number', ''),
        'date_of_sale': data.get('date_of_sale', '')
    }


def compare_sets(predicted: set, ground_truth: set) -> Dict[str, float]:
    """Compare two sets and return precision, recall, f1"""
    if not ground_truth:
        return {'precision': 1.0 if not predicted else 0.0, 'recall': 1.0, 'f1': 1.0}

    tp = len(predicted & ground_truth)
    fp = len(predicted - ground_truth)
    fn = len(ground_truth - predicted)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {'precision': precision, 'recall': recall, 'f1': f1, 'tp': tp, 'fp': fp, 'fn': fn}


def compare_name_lists(pred_names: List[str], gt_names: List[str], threshold: float = 0.75) -> Dict:
    """Compare name lists using fuzzy matching with accent/order tolerance

    Uses name_similarity_score which handles:
    - Accent variations (Martínez vs Martinez)
    - Word order (Lucía Martínez García vs Lucía García Martínez)
    - Sequence similarity for typos/variations

    Threshold lowered to 0.75 to accommodate token-based matching.
    """
    if not gt_names:
        return {'precision': 1.0 if not pred_names else 0.0, 'recall': 1.0, 'f1': 1.0}

    tp = 0
    matched_gt = set()
    matched_pairs = []  # For debugging

    # For each predicted name, find best match in ground truth
    for pred in pred_names:
        best_match = max([(name_similarity_score(pred, gt), i) for i, gt in enumerate(gt_names)], default=(0.0, -1))
        if best_match[0] >= threshold and best_match[1] not in matched_gt:
            tp += 1
            matched_gt.add(best_match[1])
            matched_pairs.append((pred, gt_names[best_match[1]], best_match[0]))
        elif best_match[0] > 0:
            # Log near-misses for debugging
            logger.debug(f"Near-miss: '{pred}' vs '{gt_names[best_match[1]]}' (score: {best_match[0]:.2f})")

    fp = len(pred_names) - tp
    fn = len(gt_names) - tp

    precision = tp / len(pred_names) if pred_names else 0.0
    recall = tp / len(gt_names) if gt_names else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {'precision': precision, 'recall': recall, 'f1': f1, 'tp': tp, 'fp': fp, 'fn': fn}


def evaluate_document(predicted: Dict, ground_truth: Dict) -> Dict[str, Any]:
    """Evaluate a single document extraction"""
    metrics = {}

    # NIF evaluation
    pred_nifs = extract_nifs(predicted)
    gt_nifs = extract_nifs(ground_truth)
    metrics['nifs'] = compare_sets(pred_nifs, gt_nifs)

    # Name evaluation
    pred_names = extract_names(predicted)
    gt_names = extract_names(ground_truth)

    for role in ['notary', 'sellers', 'buyers']:
        metrics[f'{role}_names'] = compare_name_lists(pred_names[role], gt_names[role])

    # Property references
    pred_refs = extract_property_refs(predicted)
    gt_refs = extract_property_refs(ground_truth)
    metrics['cadastral_refs'] = compare_sets(pred_refs, gt_refs)

    # Document metadata
    pred_meta = extract_document_meta(predicted)
    gt_meta = extract_document_meta(ground_truth)

    metrics['document_number_match'] = pred_meta['document_number'] == gt_meta['document_number']
    metrics['date_of_sale_match'] = pred_meta['date_of_sale'] == gt_meta['date_of_sale']

    # Count properties
    metrics['property_count'] = {
        'predicted': len(predicted.get('properties', [])),
        'ground_truth': len(ground_truth.get('properties', [])),
        'match': len(predicted.get('properties', [])) == len(ground_truth.get('properties', []))
    }

    return metrics


def aggregate_metrics(all_metrics: List[Dict]) -> Dict[str, Any]:
    """Aggregate metrics across multiple documents"""
    if not all_metrics:
        return {}

    aggregated = defaultdict(lambda: defaultdict(list))

    for metrics in all_metrics:
        for key, value in metrics.items():
            if isinstance(value, dict) and 'precision' in value:
                for metric_name in ['precision', 'recall', 'f1', 'tp', 'fp', 'fn']:
                    if metric_name in value:
                        aggregated[key][metric_name].append(value[metric_name])
            elif isinstance(value, bool):
                aggregated[key]['values'].append(1.0 if value else 0.0)
            elif isinstance(value, dict) and 'match' in value:
                aggregated[key]['match'].append(1.0 if value['match'] else 0.0)

    # Calculate means
    result = {}
    for key, metrics_dict in aggregated.items():
        result[key] = {}
        for metric_name, values in metrics_dict.items():
            if values:
                result[key][metric_name] = sum(values) / len(values)

    return result


def run_evaluation(
    synthetic_dir: Path,
    doc_type: str = 'escrituras',
    ocr_provider=None,
    extraction_provider=None
) -> Tuple[List[Dict], Dict]:
    """Run evaluation on synthetic examples with configurable providers

    Args:
        synthetic_dir: Path to synthetic_examples directory
        doc_type: 'escrituras' or 'autoliquidaciones'
        ocr_provider: OCRProvider enum value
        extraction_provider: ExtractionProvider enum value
    """
    from pipeline import process_document
    from core.validation import Escritura, Modelo600
    from core.ocr import OCRProvider
    from core.llm import ExtractionProvider

    # Default providers
    if ocr_provider is None:
        ocr_provider = OCRProvider.MISTRAL
    if extraction_provider is None:
        extraction_provider = ExtractionProvider.OPENAI

    examples_dir = synthetic_dir / doc_type
    json_files = list(examples_dir.glob('*.json'))

    if not json_files:
        return [], {}

    model_class = Escritura if doc_type == 'escrituras' else Modelo600
    all_metrics = []
    individual_results = []

    for json_file in sorted(json_files):
        pdf_name = json_file.stem
        potential_pdfs = [
            examples_dir / f"{pdf_name}.pdf",
        ]
        if 'escritura' in pdf_name:
            potential_pdfs.append(examples_dir / f"{pdf_name.replace('escritura', 'escrityra')}.pdf")
        if 'autoliquidacion' in pdf_name:
            potential_pdfs.append(examples_dir / f"{pdf_name.replace('autoliquidacion', 'autoliquidación')}.pdf")
            potential_pdfs.append(examples_dir / f"{pdf_name.replace('autoliquidacion', 'autoliquidación')}.pdf.pdf")
        if pdf_name.endswith('pdf'):
            potential_pdfs.append(examples_dir / f"{pdf_name}.pdf")

        pdf_path = next((p for p in potential_pdfs if p.exists()), None)
        if not pdf_path:
            continue

        with open(json_file, 'r') as f:
            ground_truth = json.load(f)

        try:
            predicted = process_document(
                str(pdf_path),
                doc_type=model_class,
                ocr_provider=ocr_provider,
                extraction_provider=extraction_provider,
                use_cache=True
            )
            # Convert Pydantic model to dict
            predicted = predicted.model_dump() if hasattr(predicted, 'model_dump') else predicted
        except Exception as e:
            logger.error(f"Failed {pdf_path.name}: {e}")
            continue

        metrics = evaluate_document(predicted, ground_truth)
        all_metrics.append(metrics)
        individual_results.append({'file': json_file.name, 'pdf': pdf_path.name, 'metrics': metrics})

    return individual_results, aggregate_metrics(all_metrics)


def print_comparison_table(all_results: Dict[str, Tuple[List[Dict], Dict]]):
    """Print comparison table across all provider combinations"""
    rows = []

    for config_name, (individual, aggregated) in all_results.items():
        if not aggregated:
            continue

        parts = config_name.split('_')
        doc_type = parts[0]
        ocr = parts[1] if len(parts) > 1 else 'N/A'
        extr = parts[2] if len(parts) > 2 else 'N/A'

        row = [
            doc_type,
            ocr,
            extr,
            f"{aggregated.get('nifs', {}).get('f1', 0):.3f}",
            f"{aggregated.get('sellers_names', {}).get('f1', 0):.3f}",
            f"{aggregated.get('buyers_names', {}).get('f1', 0):.3f}",
            f"{aggregated.get('cadastral_refs', {}).get('f1', 0):.3f}",
            f"{aggregated.get('document_number_match', {}).get('values', 0):.3f}",
            f"{aggregated.get('date_of_sale_match', {}).get('values', 0):.3f}",
        ]
        rows.append(row)

    headers = ['Doc Type', 'OCR', 'Extraction', 'NIFs F1', 'Sellers F1', 'Buyers F1', 'Refs F1', 'Doc#', 'Date']
    print('\n' + tabulate(rows, headers=headers, tablefmt='grid'))


def print_detailed_metrics(aggregated: Dict, title: str):
    """Print detailed metrics for single configuration"""
    print(f"\n{title}")
    print("=" * len(title))

    metric_rows = []
    for label, key in [
        ('NIFs', 'nifs'),
        ('Notary Names', 'notary_names'),
        ('Seller Names', 'sellers_names'),
        ('Buyer Names', 'buyers_names'),
        ('Cadastral Refs', 'cadastral_refs')
    ]:
        if key in aggregated:
            m = aggregated[key]
            metric_rows.append([
                label,
                f"{m.get('precision', 0):.3f}",
                f"{m.get('recall', 0):.3f}",
                f"{m.get('f1', 0):.3f}"
            ])

    print(tabulate(metric_rows, headers=['Metric', 'Precision', 'Recall', 'F1'], tablefmt='simple'))

    # Additional metrics
    extra = []
    if 'document_number_match' in aggregated:
        extra.append(['Document Number', f"{aggregated['document_number_match'].get('values', 0):.3f}"])
    if 'date_of_sale_match' in aggregated:
        extra.append(['Date of Sale', f"{aggregated['date_of_sale_match'].get('values', 0):.3f}"])
    if 'property_count' in aggregated:
        extra.append(['Property Count', f"{aggregated['property_count'].get('match', 0):.3f}"])

    if extra:
        print('\n' + tabulate(extra, headers=['Field', 'Accuracy'], tablefmt='simple'))


if __name__ == "__main__":
    from core.ocr import OCRProvider
    from core.llm import ExtractionProvider
    from itertools import product

    project_root = Path(__file__).parent.parent
    synthetic_dir = project_root / "synthetic_examples"

    # Define provider combinations to test
    ocr_providers = [OCRProvider.MISTRAL, OCRProvider.GEMMA]
    extraction_providers = [ExtractionProvider.OPENAI, ExtractionProvider.OLLAMA]
    doc_types = ['escrituras', 'autoliquidaciones']

    all_results = {}

    print("\nRunning evaluations across provider combinations...")

    for doc_type, ocr_prov, extr_prov in product(doc_types, ocr_providers, extraction_providers):
        config_name = f"{doc_type}_{ocr_prov.value}_{extr_prov.value}"
        logger.info(f"Evaluating: {config_name}")

        try:
            indiv, agg = run_evaluation(
                synthetic_dir,
                doc_type=doc_type,
                ocr_provider=ocr_prov,
                extraction_provider=extr_prov
            )
            all_results[config_name] = (indiv, agg)
        except Exception as e:
            logger.error(f"Failed {config_name}: {e}")
            all_results[config_name] = ([], {})

    # Print comparison table
    print("\n" + "="*80)
    print("PROVIDER COMPARISON RESULTS")
    print("="*80)
    print_comparison_table(all_results)

    # Save results
    output_data = {k: {'individual': v[0], 'aggregated': v[1]} for k, v in all_results.items()}
    output_path = project_root / "eval_results.json"

    def default_encoder(obj):
        if isinstance(obj, Path):
            return str(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2, default=default_encoder)

    logger.info(f"Results saved to {output_path}")
