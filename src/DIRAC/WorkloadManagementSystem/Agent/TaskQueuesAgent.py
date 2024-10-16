""" The TaskQueuesAgent will update TQs

.. literalinclude:: ../ConfigTemplate.cfg
  :start-after: ##BEGIN TaskQueuesAgent
  :end-before: ##END
  :dedent: 2
  :caption: TaskQueuesAgent options

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

__RCSID__ = "$Id$"

from DIRAC import S_OK
from DIRAC.Core.Base.AgentModule import AgentModule
from DIRAC.WorkloadManagementSystem.DB.TaskQueueDB import TaskQueueDB


class TaskQueuesAgent(AgentModule):
    """Agent for recalculating TQ shares"""

    def __init__(self, *args, **kwargs):
        """c'tor"""
        AgentModule.__init__(self, *args, **kwargs)

        # clients
        self.tqDB = None

    def initialize(self):
        """just initialize TQDB"""
        self.tqDB = TaskQueueDB()
        return S_OK()

    def execute(self):
        """calls TQDB.recalculateTQSharesForAll"""
        res = self.tqDB.recalculateTQSharesForAll()
        if not res["OK"]:
            self.log.error("Error recalculating TQ shares", res["Message"])

        return S_OK()
