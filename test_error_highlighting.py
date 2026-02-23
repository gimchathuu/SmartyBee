from vision_engine import calculate_score
import json

def test_error_detection():
    # 1. Define a simple vertical line template
    template_path = [{'x': 0.5, 'y': 0.0}, {'x': 0.5, 'y': 1.0}]
    
    print("Testing Error Highlighting Logic...")
    
    # CASE 1: Perfect Match
    print("\n--- Case 1: Perfect Match ---")
    score_perfect, errors_perfect = calculate_score(template_path, template_path)
    print(f"Score: {score_perfect}")
    print(f"Errors: {errors_perfect}")
    
    if len(errors_perfect) == 0 and score_perfect > 95:
        print("✅ SUCCESS: Perfect match has 0 errors.")
    else:
        print("❌ FAILURE: Perfect match should have 0 errors.")
        
    # CASE 2: Gross Mismatch
    print("\n--- Case 2: Gross Mismatch ---")
    user_path_bad = [
        {'x': 0.0, 'y': 0.0}, 
        {'x': 1.0, 'y': 1.0} 
    ] 
    # Diagonal vs Vertical.
    # Should highlight errors.
    
    score_bad, errors_bad = calculate_score(user_path_bad, template_path)
    print(f"Score: {score_bad}")
    print(f"Errors: {errors_bad}")
    
    if len(errors_bad) > 0:
        print(f"✅ SUCCESS: Mismatch detected {len(errors_bad)} errors.")
    else:
        print("❌ FAILURE: Gross mismatch returned 0 errors.")

if __name__ == "__main__":
    test_error_detection()
