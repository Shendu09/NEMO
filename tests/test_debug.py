"""Quick diagnostic test."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

print("Testing imports...")
try:
    from core.security import SecurityGateway, Role, ActionCategory
    print(f"✓ Imports successful")
    print(f"  ActionCategory.FILE_READ = {ActionCategory.FILE_READ}")
    print(f"  ActionCategory.FILE_READ.value = {ActionCategory.FILE_READ.value}")
    print(f"  Has .value attr: {hasattr(ActionCategory.FILE_READ, 'value')}")
    
    # Test gateway creation
    import tempfile
    tmp = tempfile.mkdtemp()
    gw = SecurityGateway(data_dir=Path(tmp), dry_run=True)
    print(f"✓ Gateway created")
    
    # Test user creation
    gw.add_user("test", "Test User", Role.ADMIN)
    print(f"✓ User created")
    
    # Test a simple operation
    result = gw.read_file("test", "/tmp/test.txt")
    print(f"✓ Operation succeeded: {result.success}")
    
except Exception as e:
    import traceback
    print(f"✗ Error: {e}")
    traceback.print_exc()
