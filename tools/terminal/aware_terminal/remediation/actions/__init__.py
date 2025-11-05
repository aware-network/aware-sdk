from .tmux_service import TmuxServiceActionFactory
from .gnome_window import GnomeWindowActionFactory
from .providers import provider_actions_factory

ACTION_FACTORIES = [
    TmuxServiceActionFactory,
    GnomeWindowActionFactory,
    provider_actions_factory,
]

def register_default_actions(register):
    for factory in ACTION_FACTORIES:
        register(factory)
