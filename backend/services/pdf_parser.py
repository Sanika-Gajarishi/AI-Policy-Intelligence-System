import pdfplumber
import fitz  # PyMuPDF
import os

# Tesseract is loaded lazily — only when a scanned PDF page needs OCR.
# Loading it at module level costs 150-400MB on every restart.
_tesseract_configured = False

def _get_tesseract():
    global _tesseract_configured
    if not _tesseract_configured:
        try:
            import pytesseract
            custom_path = os.getenv("TESSERACT_CMD")  # set this in Render env vars for local dev
            if custom_path and os.path.exists(custom_path):
                pytesseract.pytesseract.tesseract_cmd = custom_path
            _tesseract_configured = True
            print("[OK] Tesseract OCR configured (lazy)")
        except ImportError:
            print("[WARNING] pytesseract not installed — OCR disabled")
            return None
        except Exception as e:
            print(f"[WARNING] Tesseract configuration failed: {e}")
            return None
    try:
        import pytesseract
        return pytesseract
    except ImportError:
        return None

def extract_text_from_pdf(file_path):
    try:
        text = ""

        # First try with pdfplumber for text-based PDFs
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""

        # If no text found, try with PyMuPDF for image-based PDFs
        if not text.strip():
            print(f"No text found with pdfplumber, trying PyMuPDF...")
            doc = fitz.open(file_path)
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Try to get text first
                page_text = page.get_text()
                if page_text.strip():
                    text += page_text
                else:
                    # If no text, try OCR (if available)
                    try:
                        # Get page as image
                        pix = page.get_pixmap()
                        img_data = pix.tobytes("png")
                        
                        # Try OCR with pytesseract if available
                        pytesseract = _get_tesseract()
                        if pytesseract is not None:
                            from PIL import Image
                            import io
                            
                            img = Image.open(io.BytesIO(img_data))
                            ocr_text = pytesseract.image_to_string(img)
                            if ocr_text.strip():
                                text += ocr_text
                                print(f"OCR extracted {len(ocr_text)} characters from page {page_num + 1}")
                        # except ImportError:
                        #     print(f"pytesseract not available, skipping OCR for page {page_num + 1}")
                        # except Exception as ocr_error:
                        #     print(f"OCR failed for page {page_num + 1}: {ocr_error}")
                            
                    except Exception as img_error:
                        print(f"Failed to process page {page_num + 1} as image: {img_error}")
            
            doc.close()

        if not text.strip():
            raise Exception("Empty PDF or no readable text (OCR also failed)")

        print(f"Successfully extracted {len(text)} characters from PDF")
        return text

    except Exception as e:
        raise Exception(f"Invalid PDF file: {str(e)}")