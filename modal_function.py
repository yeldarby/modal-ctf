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
        # Handle the code execution
        code = code.strip()
        if not code:
            result = None
        else:
            # Try to compile the entire code block first
            try:
                # Try to compile as 'exec' mode (statements)
                compiled = compile(code, '<string>', 'exec')
                exec(compiled)
                
                # If the last line looks like an expression, try to evaluate it
                lines = code.split('\n')
                if lines:
                    last_line = lines[-1].strip()
                    if last_line and not any(last_line.startswith(kw) for kw in 
                        ['import ', 'from ', 'def ', 'class ', 'if ', 'for ', 'while ', 'with ', 'try:', 'except']):
                        try:
                            # Try to evaluate the last line as an expression
                            result = eval(last_line)
                        except:
                            # Last line wasn't an expression, that's fine
                            pass
            except SyntaxError:
                # Maybe it's a single expression?
                try:
                    result = eval(code)
                except:
                    # Re-raise the original error
                    raise
                    
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
