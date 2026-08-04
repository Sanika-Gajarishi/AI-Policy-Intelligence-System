#!/usr/bin/env python3
"""
Configure Tesseract OCR for the system
"""
import os
import sys

def test_tesseract_configuration():
    print("=" * 60)
    print("TESSERACT OCR CONFIGURATION TEST")
    print("=" * 60)
    
    # Test 1: Check if pytesseract is installed
    try:
        import pytesseract
        print("✅ pytesseract package is installed")
    except ImportError:
        print("❌ pytesseract package not found")
        print("Install with: pip install pytesseract")
        return False
    
    # Test 2: Check current Tesseract path configuration
    try:
        current_cmd = pytesseract.pytesseract.tesseract_cmd
        print(f"📍 Current Tesseract path: {current_cmd}")
    except:
        print("❌ Cannot read current Tesseract path")
    
    # Test 3: Check if Tesseract executable exists at your path
    your_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if os.path.exists(your_path):
        print(f"✅ Tesseract executable found at: {your_path}")
    else:
        print(f"❌ Tesseract executable NOT found at: {your_path}")
        print("Please verify the installation path")
        return False
    
    # Test 4: Try to set the path
    try:
        pytesseract.pytesseract.tesseract_cmd = your_path
        print("✅ Tesseract path configured successfully")
    except Exception as e:
        print(f"❌ Failed to set Tesseract path: {e}")
        return False
    
    # Test 5: Test OCR functionality
    try:
        from PIL import Image
        import io
        
        # Create a simple test image
        img = Image.new('RGB', (100, 30), color='white')
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(img)
        
        # Add text to image
        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except:
            font = ImageFont.load_default()
        
        draw.text((10, 10), "Test OCR", fill='black', font=font)
        
        # Convert to bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        # Test OCR
        result = pytesseract.image_to_string(Image.open(img_bytes))
        if result.strip():
            print(f"✅ OCR test successful: '{result.strip()}'")
            return True
        else:
            print("❌ OCR test returned empty text")
            return False
            
    except Exception as e:
        print(f"❌ OCR test failed: {e}")
        return False

def create_tesseract_config():
    """Create a permanent Tesseract configuration file"""
    config_content = '''"""
Tesseract OCR Configuration for AI Policy Dashboard
"""

import os
import pytesseract

# Set Tesseract executable path
TESSERACT_PATH = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'

if os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
    print(f"✅ Tesseract configured: {TESSERACT_PATH}")
else:
    print(f"❌ Tesseract not found at: {TESSERACT_PATH}")
    print("Please install Tesseract or update the path")
'''
    
    config_file = "tesseract_config.py"
    with open(config_file, 'w') as f:
        f.write(config_content)
    
    print(f"\n📝 Configuration file created: {config_file}")
    print("Add this to your main application if needed")

def main():
    print("Configuring Tesseract OCR for AI Policy Dashboard...")
    
    # Test current configuration
    success = test_tesseract_configuration()
    
    if success:
        print("\n🎉 Tesseract OCR is ready!")
        print("✅ Scanned PDFs will now be processed correctly")
        
        # Create permanent config
        create_tesseract_config()
        
        print("\n📋 Next Steps:")
        print("1. Restart your backend server")
        print("2. Upload scanned PDFs to test OCR")
        print("3. Check vector store health with: python monitor_vector_store.py")
        
    else:
        print("\n⚠️ Tesseract configuration failed")
        print("Please check:")
        print("1. Tesseract installation path")
        print("2. System PATH environment variable")
        print("3. pytesseract package installation")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
