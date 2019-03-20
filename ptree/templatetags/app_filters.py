from django import template
import markdown2
from django.utils.html import format_html

register = template.Library()

@register.filter
def md_html(md):
    return format_html(markdown2.markdown(md).replace('{', '{{').replace('}', '}}'))

# Filter the tree to show only a certain number of parents based on the project level
@register.simple_tag
def node_filter(project, node, state):
    span = project - node
    n_parent = 2
    if span >= -n_parent and state != 'pending':
        return True
    return False


# Filter active nodes from a list of nodes
@register.simple_tag
def active(nodes):
    return [n for n in nodes if n.state != 'pending']
