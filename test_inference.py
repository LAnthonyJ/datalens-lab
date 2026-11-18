"""Run the same offline preflight as the Gradio app."""
import sys
from demo import main

if __name__ == "__main__":
    main(["--check", *sys.argv[1:]])
