import ast
import streamlit as st
import traceback


try:
    from black import format_str, Mode
except ImportError:
    format_str = None
    Mode = None


#  AST HELPERS
def safe_unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        import astor
        return astor.to_source(node)


def max_loop_nesting(node: ast.AST) -> int:
    max_depth = 0

    def visit(n: ast.AST, depth: int):
        nonlocal max_depth
        if isinstance(n, (ast.For, ast.While)):
            depth += 1
            max_depth = max(max_depth, depth)
        for child in ast.iter_child_nodes(n):
            visit(child, depth)

    visit(node, 0)
    return max_depth


def find_string_concat_in_loops(module: ast.Module):
    results = []

    class V(ast.NodeVisitor):
        def visit_AugAssign(self, node):
            if isinstance(node.op, ast.Add) and isinstance(node.target, ast.Name):
                results.append((node.lineno, node.target.id))
            self.generic_visit(node)

    V().visit(module)
    return results


def find_list_append_patterns(module: ast.Module):
    results = []

    class V(ast.NodeVisitor):
        def visit_Call(self, node):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr == "append" and isinstance(node.func.value, ast.Name):
                    results.append((node.lineno, node.func.value.id))
            self.generic_visit(node)

    V().visit(module)
    return results


def find_range_len_patterns(module: ast.Module):
    results = []

    class V(ast.NodeVisitor):
        def visit_For(self, node):
            it = node.iter
            if isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == "range":
                if it.args and isinstance(it.args[0], ast.Call):
                    if isinstance(it.args[0].func, ast.Name) and it.args[0].func.id == "len":
                        if it.args[0].args and isinstance(it.args[0].args[0], ast.Name):
                            results.append((node.lineno, it.args[0].args[0].id))
            self.generic_visit(node)

    V().visit(module)
    return results


def find_sorted_in_loops(module: ast.Module):
    results = []

    class V(ast.NodeVisitor):
        def visit_Call(self, node):
            if isinstance(node.func, ast.Name) and node.func.id == "sorted":
                results.append(node.lineno)
            if isinstance(node.func, ast.Attribute) and node.func.attr == "sort":
                results.append(node.lineno)
            self.generic_visit(node)

    V().visit(module)
    return results


def detect_membership_of_list_in_loops(module: ast.Module):
    results = []

    class V(ast.NodeVisitor):
        def visit_Compare(self, node):
            for op in node.ops:
                if isinstance(op, ast.In):
                    if node.comparators and isinstance(node.comparators[0], ast.Name):
                        results.append((node.lineno, node.comparators[0].id))
            self.generic_visit(node)

    V().visit(module)
    return results


def estimate_time_complexity(module: ast.Module):
    max_loops = max_loop_nesting(module)
    sort_lines = find_sorted_in_loops(module)
    if max_loops == 0:
        time_est = "O(n) or O(1) (no loops detected)"
    elif max_loops == 1:
        time_est = "Heuristic: O(n) (one loop)."
    else:
        time_est = f"Heuristic: O(n^{max_loops}) (max loop nesting={max_loops})"
    if sort_lines:
        time_est += f" Sorting detected at lines {sort_lines} (O(n log n))."

    return time_est, {"max_loop_nesting": max_loops, "sort_calls": sort_lines}


def estimate_space_complexity(module: ast.Module):
    comp_count = 0
    appends = find_list_append_patterns(module)

    class V(ast.NodeVisitor):
        def visit_ListComp(self, node):
            nonlocal comp_count
            comp_count += 1
            self.generic_visit(node)

    V().visit(module)
    if comp_count > 0 or appends:
        space_est = "Heuristic: O(n) (building new containers)."
    else:
        space_est = "Heuristic: O(1) (no major containers built)."

    return space_est, {"list_comprehensions": comp_count, "list_appends": appends}


# ANALYZER
def analyze_code(code_str):
    try:
        module = ast.parse(code_str)
    except SyntaxError as e:
        return {"ok": False, "parse_error": str(e)}

    result = {"ok": True, "detections": []}

    time_est, time_details = estimate_time_complexity(module)
    space_est, space_details = estimate_space_complexity(module)

    result["time_estimate"] = time_est
    result["time_details"] = time_details
    result["space_estimate"] = space_est
    result["space_details"] = space_details

    for lineno, var in find_string_concat_in_loops(module):
        result["detections"].append({
            "type": "string_concat_in_loop",
            "lineno": lineno,
            "variable": var,
            "suggestion": "Use ''.join(...) instead of += in a loop."
        })

    for lineno, var in find_list_append_patterns(module):
        result["detections"].append({
            "type": "list_append",
            "lineno": lineno,
            "list_name": var,
            "suggestion": "Consider using a list comprehension instead of append in loop."
        })

    for lineno, seq in find_range_len_patterns(module):
        result["detections"].append({
            "type": "range_len",
            "lineno": lineno,
            "sequence": seq,
            "suggestion": "Use enumerate() instead of range(len(...))."
        })

    for lineno, container in detect_membership_of_list_in_loops(module):
        result["detections"].append({
            "type": "membership_test",
            "lineno": lineno,
            "container": container,
            "suggestion": "Convert list to set for faster membership tests."
        })

    for lineno in find_sorted_in_loops(module):
        result["detections"].append({
            "type": "sort_in_loop",
            "lineno": lineno,
            "suggestion": "Move sorting outside loop to avoid O(n log n) each iteration."
        })

    return result


#  REFACTOR 
def auto_refactor(code_str: str) -> str:
    module = ast.parse(code_str)

    class Transformer(ast.NodeTransformer):
        def visit_Module(self, node):
            new_body = []
            i = 0
            while i < len(node.body):
                cur = node.body[i]
                if (
                    isinstance(cur, ast.Assign)
                    and len(cur.targets) == 1
                    and isinstance(cur.targets[0], ast.Name)
                ):
                    varname = cur.targets[0].id
                    if (
                        isinstance(cur.value, ast.List) and not cur.value.elts
                    ) and i + 1 < len(node.body) and isinstance(node.body[i + 1], ast.For):
                        fnode = node.body[i + 1]
                        if (
                            len(fnode.body) == 1
                            and isinstance(fnode.body[0], ast.Expr)
                            and isinstance(fnode.body[0].value, ast.Call)
                        ):
                            call = fnode.body[0].value
                            if (
                                isinstance(call.func, ast.Attribute)
                                and call.func.attr == "append"
                                and isinstance(call.func.value, ast.Name)
                                and call.func.value.id == varname
                            ):
                                elt = call.args[0]
                                comp = ast.ListComp(
                                    elt=elt,
                                    generators=[ast.comprehension(target=fnode.target, iter=fnode.iter, ifs=[], is_async=0)],
                                )
                                assign = ast.Assign(targets=[ast.Name(id=varname, ctx=ast.Store())], value=comp)
                                new_body.append(assign)
                                i += 2
                                continue
                new_body.append(cur)
                i += 1
            node.body = new_body
            return node

    new_module = Transformer().visit(module)
    ast.fix_missing_locations(new_module)
    code_out = safe_unparse(new_module)
    if format_str:
        try:
            code_out = format_str(code_out, mode=Mode())
        except Exception:
            pass
    return code_out


# STREAMLIT APP 
st.set_page_config(page_title="AI Python Code Optimizer", layout="wide")

st.title("AI Python Code Optimizer")
st.write("Paste Python code, get static analysis + safe auto-refactor.")

default_example = """result = []
for x in items:
    result.append(f(x))

s = ''
for x in words:
    s += x

for i in range(len(arr)):
    print(arr[i])
"""

code = st.text_area("Paste Python code here:", value=default_example, height=300)

col1, col2 = st.columns([1, 1])

with col1:
    if st.button("Analyze Code"):
        try:
            analysis = analyze_code(code)
            if not analysis["ok"]:
                st.error("Parse error: " + analysis.get("parse_error", ""))
            else:
                st.subheader("Complexity Estimates")
                st.write("**Time:**", analysis["time_estimate"])
                st.json(analysis["time_details"])
                st.write("**Space:**", analysis["space_estimate"])
                st.json(analysis["space_details"])
                st.subheader("Detections & Suggestions")
                if analysis["detections"]:
                    for d in analysis["detections"]:
                        st.markdown(f"- **{d['type']}** (line {d['lineno']}): {d['suggestion']}")
                else:
                    st.info("No issues detected.")
        except Exception:
            st.error("Analysis failed")
            st.text(traceback.format_exc())

with col2:
    if st.button("Auto-Refactor"):
        try:
            new_code = auto_refactor(code)
            st.subheader("Refactored Code")
            st.code(new_code, language="python")
            st.download_button("Download Refactored Code", new_code, file_name="refactored_code.py")
        except Exception:
            st.error("Refactor failed")
            st.text(traceback.format_exc())
