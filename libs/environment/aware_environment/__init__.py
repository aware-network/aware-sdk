"""Core environment registries for Aware agents, roles, rules, and objects."""

from .agent.registry import AgentRegistry
from .agent.spec import AgentSpec
from .doc.fragments import (
    DocsApplyReceipt,
    FragmentApplyResult,
    FragmentApplyStatus,
    RenderedFragment,
    apply_fragments,
    render_fragments,
    render_fragment_for_attributes,
)
from .doc.markers import BEGIN_MARKER, END_MARKER, format_begin_marker, parse_begin_marker
from .environment import Environment, load_environment
from .exceptions import DuplicateSpecError, EnvironmentLoadError, RegistryError, UnknownSpecError
from .object.registry import ObjectRegistry
from .object.spec import ObjectFunctionSpec, ObjectSpec
from .role.registry import RoleRegistry
from .role.spec import RoleSpec
from .rule.registry import RuleRegistry
from .rule.spec import RuleSpec
from .protocol.registry import ProtocolRegistry
from .protocol.spec import ProtocolSpec, ProtocolTarget
from .pathspec import PathSpec, Visibility, resolve_pathspec
from .locks import compute_env_lock, compute_rules_lock
from .seed import seed_environment, iter_pathspecs
from .panel import PanelManifest, validate_panel_manifest
from .acl import AccessRequest, AccessDecision, AccessSnapshot, evaluate_access
from .renderer import (
    ReferenceEntry,
    render_rules,
    render_rule_fragments,
    render_agent_document,
    render_role_bundle,
    render_function,
    render_section,
)
from .summary import (
    ContentChainEntry,
    DocSummary,
    SummaryBlock,
    SummaryDocument,
    SummaryEvent,
    build_content_chain_map,
    build_summary_blocks,
    colorize_badges,
    derive_doc_label,
    format_doc_summary_line,
    format_snapshot_label,
    render_summary_text,
)

__all__ = [
    "AgentRegistry",
    "AgentSpec",
    "DuplicateSpecError",
    "Environment",
    "EnvironmentLoadError",
    "load_environment",
    "BEGIN_MARKER",
    "END_MARKER",
    "format_begin_marker",
    "parse_begin_marker",
    "RenderedFragment",
    "FragmentApplyStatus",
    "FragmentApplyResult",
    "DocsApplyReceipt",
    "render_fragments",
    "render_fragment_for_attributes",
    "apply_fragments",
    "ObjectFunctionSpec",
    "ObjectRegistry",
    "ObjectSpec",
    "RegistryError",
    "RoleRegistry",
    "RoleSpec",
    "RuleRegistry",
    "RuleSpec",
    "ProtocolRegistry",
    "ProtocolSpec",
    "ProtocolTarget",
    "PathSpec",
    "Visibility",
    "resolve_pathspec",
    "compute_env_lock",
    "compute_rules_lock",
    "seed_environment",
    "iter_pathspecs",
    "PanelManifest",
    "validate_panel_manifest",
    "AccessRequest",
    "AccessDecision",
    "AccessSnapshot",
    "evaluate_access",
    "render_rules",
    "render_rule_fragments",
    "render_function",
    "render_section",
    "render_agent_document",
    "render_role_bundle",
    "ReferenceEntry",
    "SummaryDocument",
    "SummaryEvent",
    "DocSummary",
    "SummaryBlock",
    "ContentChainEntry",
    "build_summary_blocks",
    "render_summary_text",
    "format_doc_summary_line",
    "colorize_badges",
    "format_snapshot_label",
    "derive_doc_label",
    "build_content_chain_map",
    "UnknownSpecError",
    "__version__",
]

__version__ = "0.1.3"
