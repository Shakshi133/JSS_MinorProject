🧠 AI Python Code Optimizer

An interactive Streamlit app that analyzes Python code for time & space complexity, detects common anti-patterns, and applies safe auto-refactors (like converting simple loops into list comprehensions).

⚡ Built with AST parsing + static analysis (no execution, safe to use).

🚀 Features

✅ Static Analysis – Estimates time & space complexity using AST patterns.

✅ Anti-Pattern Detection –

list.append in loops → Suggest list comprehension

String concatenation in loops → Suggest "".join(...)

range(len(...)) loops → Suggest direct iteration

Nested loops & recursion → Complexity alerts

✅ Auto-Refactor (Safe Transforms) –

Converts simple list.append loops → list comprehensions

✅ Black Integration – Auto-formats refactored code (if installed).

✅ No Execution – The app never runs your code; analysis is static only.

🛠️ Installation

Clone the repo and install dependencies:

git clone https://github.com/your-username/ai-code-optimizer.git
cd ai-code-optimizer
pip install -r requirements.txt

Requirements

Python 3.8+

Streamlit

Black (optional, for formatting)

Install manually if needed:

pip install streamlit black

▶️ Usage

Run the Streamlit app:

streamlit run app.py


Open in browser → http://localhost:8501

📝 Example Code to Try

Paste this into the text area to test analysis & refactor:

result = []
for x in range(10):
    result.append(x * x)

s = ""
for w in ["a", "b", "c"]:
    s += w

arr = [10, 20, 30]
for i in range(len(arr)):
    print(arr[i])

Expected Results:

Detects list.append loop → Suggests list comprehension

Detects string concatenation in loop → Suggests "".join()

Detects range(len(...)) → Suggests direct iteration



⚠️ Limitations

Only handles simple safe refactors (not advanced optimizations).

Complexity estimates are heuristic (based on AST patterns, not proofs).

Always review refactored code before using in production.

📌 Roadmap

Add more refactor rules (e.g., map, set optimizations).

Detect unused imports & dead code.

Add AI-based optimization suggestions (LLM integration).
