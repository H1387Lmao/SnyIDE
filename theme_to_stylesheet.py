import json,os, re
l = os.path.join
def resolve_variable(match, variables):
	key = match.group(1)
	return variables.get(key, match.group(0))

def get_stylesheet(theme_path):
	base_dir = os.path.dirname(__file__)
	with open(l(base_dir,"constant_theme.css"), encoding="utf-8") as f:
		content = f.read()
	with open(theme_path, encoding="utf-8") as f:
		variables = json.load(f)
	# Replace $Token$ with values from the theme using a non-greedy, safe key pattern
	# Keys are expected to be alphanumeric/underscore identifiers
	pattern = re.compile(r"\$([A-Za-z0-9_]+)\$")
	styled = pattern.sub(lambda m: resolve_variable(m, variables), content)
	# Make icon URLs absolute so Qt can load them reliably
	icons_dir = l(base_dir, "icons").replace('\\', '/')
	styled = re.sub(r"url\((?:\./)?icons/([^)]+)\)", lambda m: f"url({icons_dir}/" + m.group(1) + ")", styled)
	return styled
