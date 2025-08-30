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
        
        # Handle the code execution
        code = code.strip()
        if not code:
            result = None
        else:
            # Try to compile the entire code block first
            try:
                # Try to compile as 'exec' mode (statements)
                compiled = compile(code, '<string>', 'exec')
                exec(compiled, exec_globals)
                
                # If the last line looks like an expression, try to evaluate it
                lines = code.split('\n')
                if lines:
                    last_line = lines[-1].strip()
                    if last_line and not any(last_line.startswith(kw) for kw in 
                        ['import ', 'from ', 'def ', 'class ', 'if ', 'for ', 'while ', 'with ', 'try:', 'except']):
                        try:
                            # Try to evaluate the last line as an expression
                            result = eval(last_line, exec_globals)
                        except:
                            # Last line wasn't an expression, that's fine
                            pass
            except SyntaxError:
                # Maybe it's a single expression?
                try:
                    result = eval(code, exec_globals)
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
