"""
Trace object types that are inserted into Python list.
"""
import ast
from .analysis import get_id
from .clike import CLikeTranspiler

def decltype(node):
    """Create C++ decltype statement"""
    if is_list(node):
        return "std::vector<decltype({0})>".format(value_type(node))
    if is_dict(node):
        if node.value.keys is not None and len(node.value.keys) > 0:
            key0 = node.value.keys[0].value
            if isinstance(key0, str) and not key0.isnumeric():
                key0 = 'std::string("{0}")'.format(key0)
            value0 = node.value.values[0].value
            if isinstance(value0, str) and not value0.isnumeric():
                value0 = 'std::string("{0}")'.format(value0)
            return "std::unordered_map<decltype({0}), decltype({1})>".format(key0,
                        value0)
        else:
            hint = f"{node.type_comment} {dir(node)}"
            return f"std::unordered_map<decltype({hint}), decltype(?)>"
    else:
        return "decltype({0})".format(value_type(node))


def is_builtin_import(name):
    return name == "sys" or name == "math"


def is_list(node):
    """Check if a node was assigned as a list"""
    if isinstance(node, ast.List):
        return True
    elif isinstance(node, ast.Assign):
        return is_list(node.value)
    elif isinstance(node, ast.Name):
        var = node.scopes.find(get_id(node))
        return (hasattr(var, "assigned_from") and not
                isinstance(var.assigned_from, ast.FunctionDef) and
                is_list(var.assigned_from.value))
    else:
        return False

def is_dict(node):
    """Check if a node was assigned as a list"""
    if isinstance(node, ast.Dict):
        return True
    elif isinstance(node, ast.Assign):
        return is_dict(node.value)
    elif isinstance(node, ast.Name):
        var = node.scopes.find(get_id(node))
        return (hasattr(var, "assigned_from") and not
                isinstance(var.assigned_from, ast.FunctionDef) and
                is_dict(var.assigned_from.value))
    else:
        return False

def value_expr(node):
    """
    Follow all assignments down the rabbit hole in order to find
    the value expression of a name.
    The boundary is set to the current scope.
    """
    return ValueExpressionVisitor().visit(node)


def value_type(node):
    """
    Guess the value type of a node based on the manipulations or assignments
    in the current scope.
    Special case: If node is a container like a list the value type inside the
    list is returned not the list type itself.
    """
    return ValueTypeVisitor().visit(node)


class ValueExpressionVisitor(ast.NodeVisitor):
    def visit_Num(self, node):
        return str(node.n)

    def visit_Str(self, node):
        return node.s

    def visit_Name(self, node):
        var = node.scopes.find(get_id(node))
        if isinstance(var.assigned_from, ast.For):
            it = var.assigned_from.iter
            return "std::declval<typename decltype({0})::value_type>()".format(
                   self.visit(it))
        elif isinstance(var.assigned_from, ast.FunctionDef):
            return get_id(var)
        else:
            return self.visit(var.assigned_from.value)

    def visit_Call(self, node):
        params = ",".join([self.visit(arg) for arg in node.args])
        return "{0}({1})".format(node.func.id, params)

    def visit_Assign(self, node):
        return self.visit(node.value)

    def visit_BinOp(self, node):
        return "{0} {1} {2}".format(self.visit(node.left),
                                    CLikeTranspiler().visit(node.op),
                                    self.visit(node.right))


class ValueTypeVisitor(ast.NodeVisitor):
    def visit_Num(self, node):
        return value_expr(node)

    def visit_Str(self, node):
        return value_expr(node)

    def visit_Name(self, node):
        if node.id == 'True' or node.id == 'False':
            return CLikeTranspiler().visit(node)

        var = node.scopes.find(node.id)
        if defined_before(var, node):
            return node.id
        else:
            return self.visit(var.assigned_from.value)

    def visit_NameConstant(self, node):
        return CLikeTranspiler().visit(node)

    def visit_Call(self, node):
        params = ",".join([self.visit(arg) for arg in node.args])
        return "{0}({1})".format(node.func.id, params)

    def visit_Assign(self, node):
        if isinstance(node.value, ast.List):
            if len(node.value.elts) > 0:
                val = node.value.elts[0]
                return self.visit(val)
            else:
                target = node.targets[0]
                var = node.scopes.find(target.id)
                first_added_value = var.calls[0].args[0]
                return value_expr(first_added_value)
        else:
            return self.visit(node.value)


def defined_before(node1, node2):
    """Check if node a has been defined before an other node b"""
    return node1.lineno < node2.lineno


def is_list_assignment(node):
    return (isinstance(node.value, ast.List) and
            isinstance(node.targets[0].ctx, ast.Store))


def is_list_addition(node):
    """Check if operation is adding something to a list"""
    list_operations = ["append", "extend", "insert"]
    return (isinstance(node.func.ctx, ast.Load) and
            hasattr(node.func, "value") and
            isinstance(node.func.value, ast.Name) and
            node.func.attr in list_operations)


def is_recursive(fun):
    finder = RecursionFinder()
    finder.visit(fun)
    return finder.recursive


class RecursionFinder(ast.NodeVisitor):
    function_name = None
    recursive = False

    def visit_FunctionDef(self, node):
        self.function_name = node.name
        self.generic_visit(node)

    def visit_Call(self, node):
        self.recursive = (isinstance(node.func, ast.Name) and
                          node.func.id == self.function_name)
        self.generic_visit(node)
