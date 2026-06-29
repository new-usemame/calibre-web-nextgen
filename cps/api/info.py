# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Info endpoints for /api/v1: About/stats + the task queue.

Reuses the legacy cores (about.collect_stats, tasks_status.render_task_status,
WorkerThread) so the SPA shows exactly what the Jinja pages show.
"""
from flask import jsonify

from . import api_v1
from .. import calibre_db, db
from ..cw_login import current_user
from ..usermanagement import login_required_if_no_ano
from ..about import collect_stats
from ..tasks_status import render_task_status
from ..services.worker import WorkerThread


@api_v1.route("/about")
@login_required_if_no_ano
def about_info():
    """Library counts + component versions (the legacy Statistics page)."""
    return jsonify({
        "counts": {
            "books": calibre_db.session.query(db.Books).count(),
            "authors": calibre_db.session.query(db.Authors).count(),
            "categories": calibre_db.session.query(db.Tags).count(),
            "series": calibre_db.session.query(db.Series).count(),
        },
        # collect_stats() returns an ordered {name: version} map.
        "versions": collect_stats(),
    })


@api_v1.route("/tasks")
@login_required_if_no_ano
def tasks_list():
    """Worker queue. render_task_status already scopes rows to the caller (own
    tasks, or all for an admin) and localizes status text."""
    worker = WorkerThread.get_instance()
    return jsonify({"items": render_task_status(worker.tasks)})


@api_v1.route("/tasks/<task_id>/cancel", methods=["POST"])
@login_required_if_no_ano
def cancel_task_api(task_id):
    """Cancel a cancellable task. A non-admin may only cancel their own task —
    we resolve the task by id and check ownership before ending it (the legacy
    /ajax/canceltask did not scope this)."""
    worker = WorkerThread.get_instance()
    target = None
    for __, user, __, task, __ in worker.tasks:
        if str(task.id) == str(task_id):
            if user == current_user.name or current_user.role_admin():
                target = task
            else:
                return jsonify({"error": {"code": "forbidden",
                                          "message": "Not your task"}}), 403
            break
    if target is None:
        return jsonify({"error": {"code": "not_found", "message": "Task not found"}}), 404
    worker.end_task(target.id)
    return "", 204
