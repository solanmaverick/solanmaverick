import pandas as pd

def verify_excel():
    print("Verifying Excel file structure and content...")
    
    # Read the test file
    df = pd.read_excel("test.xlsx")
    
    # Check columns
    print("\nColumns in test file:")
    print(df.columns.tolist())
    
    # Verify required fixed attributes
    required_attrs = ['学校名称', '专业名称', '学校代码', '专业代码', '位次差']
    missing_attrs = [attr for attr in required_attrs if attr not in df.columns]
    
    if missing_attrs:
        print("\nWARNING: Missing required attributes:", missing_attrs)
    else:
        print("\nAll required fixed attributes present ✓")
    
    # Show sample data
    print("\nSample data (first 3 rows):")
    print(df.head(3))
    
    return len(missing_attrs) == 0

if __name__ == "__main__":
    verify_excel()
