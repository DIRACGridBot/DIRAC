""" pytest for WorkflowTasks
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

# pylint: disable=protected-access,missing-docstring,invalid-name

from mock import MagicMock
import json
import pytest

from pytest import mark

parametrize = mark.parametrize

from hypothesis import given, settings, HealthCheck
from hypothesis.strategies import (
    composite,
    builds,
    integers,
    lists,
    recursive,
    floats,
    text,
    booleans,
    none,
    dictionaries,
    tuples,
    dates,
    datetimes,
    from_regex,
)
from string import ascii_letters, digits

from DIRAC.TransformationSystem.Client.RequestTasks import RequestTasks

# from DIRAC import gLogger
# from DIRAC.Interfaces.API.Job import Job

# # sut
# from DIRAC.TransformationSystem.Client.WorkflowTasks import WorkflowTasks

# gLogger.setLevel("DEBUG")


@composite
def taskStrategy(draw):
    """Generate a strategy that returns a task dictionnary"""
    transformationID = draw(integers(min_value=1))
    targetSE = ",".join(draw(lists(text(ascii_letters, min_size=5, max_size=10), min_size=1, max_size=3)))
    inputData = draw(lists(from_regex("(/[a-z]+)+", fullmatch=True), min_size=1, max_size=10))

    return {"TransformationID": transformationID, "TargetSE": targetSE, "InputData": inputData}


def taskDictStrategy():
    return dictionaries(integers(min_value=1), taskStrategy(), min_size=1, max_size=10)


mockTransClient = MagicMock()
mockReqClient = MagicMock()
mockReqValidator = MagicMock()


reqTasks = RequestTasks(
    transClient=mockTransClient,
    requestClient=mockReqClient,
    requestValidator=mockReqValidator,
)
# odm_o = MagicMock()
# odm_o.execute.return_value = {"OK": True, "Value": {}}
# wfTasks.outputDataModule_o = odm_o


@parametrize(
    "transBody",
    [
        "removal;RemoveFile",  # Transformation to remove files
        "removal;RemoveReplica",  # Transformation to remove Replicas
        "anything;ReplicateAndRegister",  # Transformation to replicate and register, first parameter is useless
        "",  # if no Body, we expect replicateAndRegister
    ],
)
@settings(max_examples=10)
@given(
    owner=text(ascii_letters + "-_" + digits, min_size=1),
    taskDict=taskDictStrategy(),
)
def test_prepareSingleOperationsBody(transBody, owner, taskDict):
    """Test different bodies that should be routed through the
    singleOperationBody method.
    """

    # keep the number of tasks for later
    originalNbOfTasks = len(taskDict)

    # Make up the DN and the group
    ownerDN = "DN_" + owner
    ownerGroup = "group_" + owner

    res = reqTasks.prepareTransformationTasks(transBody, taskDict, owner=owner, ownerGroup=ownerGroup, ownerDN=ownerDN)

    assert res["OK"], res

    # prepareTransformationTasks can pop tasks if a problem occurs,
    # so check that this did not happen
    assert len(res["Value"]) == originalNbOfTasks

    for _taskID, task in taskDict.items():

        req = task.get("TaskObject")

        # Checks whether we got a Request assigned
        assert req

        # Check that the attributes of the request are what
        # we expect them to be
        assert req.OwnerDN == ownerDN
        assert req.OwnerGroup == ownerGroup

        # Make sure we only have one operation
        assert len(req) == 1

        ops = req[0]

        # Check the operation type
        # The operation type is either given as second parameter of the body
        # or if not, it is ReplicateAndRegister

        expectedOpsType = transBody.split(";")[-1] if transBody else "ReplicateAndRegister"
        assert ops.Type == expectedOpsType

        # Check that the targetSE is set correctly
        assert ops.TargetSE == task["TargetSE"]

        # Make sure we have one file per LFN in the task
        assert len(ops) == len(task["InputData"])

        # Checks that there is one file per LFN
        assert set([f.LFN for f in ops]) == set(task["InputData"])


@parametrize(
    "transBody",
    [
        [
            ("ReplicateAndRegister", {"TargetSE": "BAR-SRM"}),
        ],
        [
            ("ReplicateAndRegister", {"TargetSE": "TASK:TargetSE"}),
        ],
        [
            ("ReplicateAndRegister", {"SourceSE": "FOO-SRM", "TargetSE": "BAR-SRM"}),
            ("RemoveReplica", {"TargetSE": "FOO-SRM"}),
        ],
        [
            ("ReplicateAndRegister", {"SourceSE": "FOO-SRM", "TargetSE": "TASK:TargetSE"}),
            ("RemoveReplica", {"TargetSE": "FOO-SRM"}),
        ],
    ],
    ids=[
        "Single operation, no substitution",
        "Single operation, with substitution",
        "Multiple operations, no substitution",
        "Multiple operations, with substitution",
    ],
)
@settings(max_examples=10)
@given(
    owner=text(ascii_letters + "-_" + digits, min_size=1),
    taskDict=taskDictStrategy(),
)
def test_prepareMultiOperationsBody(transBody, owner, taskDict):
    """Test different bodies that should be routed through the
    multiOperationsBody method.
    """

    # keep the number of tasks for later
    originalNbOfTasks = len(taskDict)

    # Make up the DN and the group
    ownerDN = "DN_" + owner
    ownerGroup = "group_" + owner

    res = reqTasks.prepareTransformationTasks(
        json.dumps(transBody), taskDict, owner=owner, ownerGroup=ownerGroup, ownerDN=ownerDN
    )

    assert res["OK"], res

    # prepareTransformationTasks can pop tasks if a problem occurs,
    # so check that this did not happen
    assert len(res["Value"]) == originalNbOfTasks

    for _taskID, task in taskDict.items():

        req = task.get("TaskObject")

        # Checks whether we got a Request assigned
        assert req

        # Check that the attributes of the request are what
        # we expect them to be
        assert req.OwnerDN == ownerDN
        assert req.OwnerGroup == ownerGroup

        # Make sure we have as many operations as tuple in the body
        assert len(req) == len(transBody)

        # Loop over each operation
        # to check their attributes
        for opsID, ops in enumerate(req):

            expectedOpsType, expectedOpsAttributes = transBody[opsID]

            # Compare the operation type with what we want
            assert ops.Type == expectedOpsType

            # Check the operation attributes one after the other
            for opsAttr, opsVal in expectedOpsAttributes.items():

                # If the expected value starts with 'TASK:'
                # we should make the substitution with whatever is in
                # the taskDict.
                # So it should be different
                if opsVal.startswith("TASK:"):
                    assert getattr(ops, opsAttr) != opsVal
                # Otherwise, make sure it matches
                else:
                    assert getattr(ops, opsAttr) == opsVal

                # Make sure we have one file per LFN in the task
                assert len(ops) == len(task["InputData"])

                # Checks that there is one file per LFN
                assert set([f.LFN for f in ops]) == set(task["InputData"])


@parametrize(
    "transBody",
    [
        [
            ("ReplicateAndRegister", {"TargetSE": "TASK:NotInTaskDict"}),
        ],
    ],
    ids=[
        "Non existing substituation",
    ],
)
@settings(max_examples=10)
@given(
    owner=text(ascii_letters + "-_" + digits, min_size=1),
    taskDict=taskDictStrategy(),
)
def test_prepareProblematicMultiOperationsBody(transBody, owner, taskDict):
    """Test different bodies that should be routed through the
    multiOperationBody method, but that have a problem
    """

    # keep the number of tasks for later
    originalNbOfTasks = len(taskDict)

    # Make up the DN and the group
    ownerDN = "DN_" + owner
    ownerGroup = "group_" + owner

    res = reqTasks.prepareTransformationTasks(
        json.dumps(transBody), taskDict, owner=owner, ownerGroup=ownerGroup, ownerDN=ownerDN
    )

    assert res["OK"], res

    # prepareTransformationTasks pop tasks if a problem occurs,
    # so make sure it happened
    assert len(res["Value"]) != originalNbOfTasks

    # Check that other tasks are fine
    for _taskID, task in taskDict.items():

        req = task.get("TaskObject")

        # Checks whether we got a Request assigned
        assert req

        # Check that the attributes of the request are what
        # we expect them to be
        assert req.OwnerDN == ownerDN
        assert req.OwnerGroup == ownerGroup

        # Make sure we have as many operations as tuple in the body
        assert len(req) == len(transBody)

        # Loop over each operation
        # to check their attributes
        for opsID, ops in enumerate(req):

            expectedOpsType, expectedOpsAttributes = transBody[opsID]

            # Compare the operation type with what we want
            assert ops.Type == expectedOpsType

            # Check the operation attributes one after the other
            for opsAttr, opsVal in expectedOpsAttributes.items():

                # If the expected value starts with 'TASK:'
                # we should make the substitution with whatever is in
                # the taskDict.
                # So it should be different
                if opsVal.startswith("TASK:"):
                    assert getattr(ops, opsAttr) != opsVal
                # Otherwise, make sure it matches
                else:
                    # Check that the targetSE is set correctly
                    assert getattr(ops, opsAttr) == opsVal

                # Make sure we have one file per LFN in the task
                assert len(ops) == len(task["InputData"])

                # Checks that there is one file per LFN
                assert set([f.LFN for f in ops]) == set(task["InputData"])
