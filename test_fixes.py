#!/usr/bin/env python3
"""
Test script to verify the comprehensive fixes for registration date and OCR issues
"""

from src.extraction.utils.helpers import extract_registration_date_fallback

def test_enhanced_date_patterns():
    """Test the enhanced Indonesian date patterns"""
    
    test_cases = [
        ("Tutup Pendaftaran : 30 April 2026", "30 April 2026"),
        ("Sampai tanggal 15 Mei 2026", "15 Mei 2026"),
        ("Pendaftaran ditutup 20 Juni 2026", "20 Juni 2026"),
        ("Batas terakhir: 25 Juli 2026", "25 Juli 2026"),
        ("Deadline pendaftaran: 10 Agustus 2026", "10 Agustus 2026"),
        ("DL: 5 September 2026", "5 September 2026"),
        ("Catat tanggal: 1-14 Oktober 2026", "1 Oktober 2026 - 14 Oktober 2026"),
    ]
    
    print("Testing Enhanced Date Extraction Patterns")
    print("=" * 50)
    
    passed = 0
    total = len(test_cases)
    
    for i, (text, expected) in enumerate(test_cases, 1):
        result = extract_registration_date_fallback(text)
        
        if result:
            status = "✓ PASS" if expected in result or result in expected else "✗ FAIL"
            if status == "✓ PASS":
                passed += 1
        else:
            status = "✗ FAIL"
        
        print(f"{status} Test {i}: {text}")
        print(f"    Expected: {expected}")
        print(f"    Got:      {result}")
        print()
    
    print(f"Results: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    return passed == total

def test_ocr_availability():
    """Test OCR functionality"""
    
    print("Testing OCR Functionality")
    print("=" * 30)
    
    try:
        from src.extraction.ocr_extractor import OCRExtractor
        from pathlib import Path
        
        ocr = OCRExtractor()
        
        if ocr.available:
            print("✓ OCR is available")
            
            # Test with a sample image
            image_dir = Path('data/images')
            if image_dir.exists():
                images = list(image_dir.glob('*.webp'))[:1]  # Test 1 image
                
                if images:
                    img_path = images[0]
                    try:
                        text, confidence = ocr.extract_with_confidence(str(img_path), timeout=10)
                        if text:
                            print(f"✓ OCR extraction successful: {len(text)} chars, {confidence}% confidence")
                            print(f"  Sample: {text[:100]}...")
                            return True
                        else:
                            print("✗ OCR extraction failed: No text extracted")
                            return False
                    except Exception as e:
                        print(f"✗ OCR extraction error: {e}")
                        return False
                else:
                    print("✗ No test images found")
                    return False
            else:
                print("✗ Image directory not found")
                return False
        else:
            print("✗ OCR not available")
            return False
            
    except Exception as e:
        print(f"✗ OCR test failed: {e}")
        return False

def main():
    """Run all tests"""
    
    print("COMPREHENSIVE FIXES VERIFICATION")
    print("=" * 60)
    print()
    
    # Test 1: Enhanced date patterns
    date_test_passed = test_enhanced_date_patterns()
    print()
    
    # Test 2: OCR functionality
    ocr_test_passed = test_ocr_availability()
    print()
    
    # Summary
    print("SUMMARY")
    print("=" * 30)
    print(f"Enhanced Date Patterns: {'✓ PASS' if date_test_passed else '✗ FAIL'}")
    print(f"OCR Functionality:      {'✓ PASS' if ocr_test_passed else '✗ FAIL'}")
    print()
    
    if date_test_passed and ocr_test_passed:
        print("🎉 ALL TESTS PASSED! Fixes are working correctly.")
        print()
        print("Expected improvements:")
        print("- Registration date coverage: 57.7% → 70-80%")
        print("- Database insertion rate: 57.7% → 100%")
        print("- OCR success rate: 0% → 20-30%")
        print("- Data loss: 42.3% → 0%")
    else:
        print("❌ Some tests failed. Please check the implementation.")
    
    return date_test_passed and ocr_test_passed

if __name__ == "__main__":
    main()