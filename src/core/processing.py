
import fitz  # PyMuPDF
from PIL import Image
import io

def get_page_as_image(page):
    """Convert PDF page to PIL Image"""
    pix = page.get_pixmap(dpi=300)
    img_bytes = pix.tobytes("png")
    image = Image.open(io.BytesIO(img_bytes))
    return image

def chunk_page(page_image, overlap_percent=10):
    """Split page image into three vertical chunks (top/mid/bottom) with overlap"""
    width, height = page_image.size
    chunk_height = height // 3
    overlap = int(chunk_height * overlap_percent / 100)

    top = page_image.crop((0, 0, width, chunk_height + overlap))
    mid = page_image.crop((0, chunk_height - overlap, width, 2 * chunk_height + overlap))
    bottom = page_image.crop((0, 2 * chunk_height - overlap, width, height))

    return [top, mid, bottom]


def process_pdf(file_path : str, sub_page_chunking=True):
    """Process PDF file and return all image chunks"""
    pdf = fitz.open(file_path)
    chunks_all_images = []

    for page in pdf.pages():
        page_image = get_page_as_image(page)
        if sub_page_chunking:
            chunks = chunk_page(page_image)
            chunks_all_images.extend(chunks)
        else:
            chunks_all_images.append(page_image)

    pdf.close()
    return chunks_all_images

if __name__ == "__main__":
    pdf_path = "/home/velocitatem/Documents/Projects/accenture_mavericks/Pdfs_prueba/Autoliquidacion.pdf"
    all_chunks = process_pdf(pdf_path)
    print(f"Generated {len(all_chunks)} chunks from PDF")
    all_chunks[0].show()
    all_chunks[3].show()
    all_chunks[4].show()
