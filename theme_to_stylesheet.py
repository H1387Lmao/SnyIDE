import json,os, re
l = os.path.join
def resolve_variable(match, variables):
	return variables.get(match.group(1), match.group(0))

def get_stylesheet(theme_path):
	with open(l(os.path.dirname(__file__),"constant_theme.css")) as f:
		content = f.read()
	with open(theme_path) as f:
		variables = json.load(f)
	return re.sub(r"\$(.+)\$", lambda m: resolve_variable(m, variables), content)
