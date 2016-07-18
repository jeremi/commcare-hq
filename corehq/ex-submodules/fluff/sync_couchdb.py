import os

from couchdbkit.ext.django.loading import get_db
# corehq dependency is simplest of a few annoying options
# - move this code into corehq
# - extract corehq.preindex into its own project
# - be ok with intentionally introducing this dependency
#   for something that's pretty bound to our specific deploy workflow
from corehq.preindex import PreindexPlugin
from dimagi.utils.couch.sync_docs import DesignInfo
from pillowtop.utils import get_all_pillow_instances


class FluffPreindexPlugin(PreindexPlugin):

    def __init__(self, app_label, file):
        self.app_label = app_label
        self.dir = os.path.abspath(os.path.dirname(file))

    def _get_designs(self):
        designs = []
        for pillow in get_all_pillow_instances():
            processor = getattr(pillow, '_processor', None)
            if processor and hasattr(processor, 'indicator_class'):
                app_label = processor.indicator_class._meta.app_label
                designs.append(DesignInfo(
                    app_label=self.app_label,
                    db=get_db(app_label),
                    design_path=os.path.join(self.dir, "_design")
                ))
        return designs


FluffPreindexPlugin.register('fluff', __file__)
