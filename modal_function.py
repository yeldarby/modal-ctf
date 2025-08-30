import modal
import traceback
import sys
import os
from io import StringIO

app = modal.App("modal-ctf-challenge")

@app.function(
    restrict_modal_access=True,  # Restrict access to Modal resources
    block_network=True,           # Block network access
    max_inputs=1,                 # Fresh container for each request
    timeout=10,                   # 10 second timeout
    cpu=0.25,                     # Minimal resources
    memory=256,                   # 256 MB memory
)
def run_untrusted_code(code: str) -> dict:
    """
    Execute untrusted Python code in a restricted environment.
    This function is intentionally vulnerable for CTF purposes.
    """
    output = StringIO()
    error = None
    result = None
    
    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = output
    
    try:
        # Show execution context to verify we're running in Modal container
        import pwd
        username = pwd.getpwuid(os.getuid()).pw_name
        print(f"Executing in container as user: {username} (uid: {os.getuid()})")
        
        # Create a restricted execution environment
        exec_globals = {
            "__builtins__": __builtins__,
            "__name__": "__main__",
        }
        
        # Execute the code and capture the last expression's value
        # Split code into lines to handle both statements and expressions
        lines = code.strip().split('\n')
        if lines:
            # Execute all lines except the last as statements
            if len(lines) > 1:
                exec('\n'.join(lines[:-1]), exec_globals)
            
            # Try to evaluate the last line as an expression
            last_line = lines[-1].strip()
            if last_line:
                try:
                    result = eval(last_line, exec_globals)
                except SyntaxError:
                    # If it's not an expression, execute it as a statement
                    exec(last_line, exec_globals)
                    
    except Exception as e:
        error = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
    finally:
        # Restore stdout
        sys.stdout = old_stdout
    
    return {
        "result": result,  # This will be pickled when returned!
        "output": output.getvalue(),
        "error": error
    }
