# LSST Data Management System
# Copyright 2015 AURA/LSST.
#
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the LSST License Statement and
# the GNU General Public License along with this program.  If not,
# see <http://www.lsstcorp.org/LegalNotices/>.

"""
This module implements the TAP and TAP-like protocols for access
to a database.

Supported formats: json and html.

@author  Jacek Becla, SLAC

"""
import logging as log
from http.client import OK, INTERNAL_SERVER_ERROR

from flask import Blueprint, request, current_app, make_response, render_template
from flask import jsonify

from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError, InterfaceError

from lsst.dax.dbserv.compat.fields import MySQLFieldHelper
from lsst.dax.webservcommon import render_response

ACCEPT_TYPES = ['application/json', 'text/html']

db_api_v0 = Blueprint('api_db_v0', __name__, static_folder='static',
                      template_folder='templates')


@db_api_v0.route('/')
def index():
    fmt = request.accept_mimetypes.best_match(ACCEPT_TYPES)
    if fmt == "text/html":
        return make_response(render_template("api_db_v0.html"))
    else:
        return jsonify({"Links": "/tap/sync"})


@db_api_v0.route('/tap/')
def tap():
    fmt = request.accept_mimetypes.best_match(ACCEPT_TYPES)
    if fmt == "text/html":
        return  "<a href='sync'>sync</a>"
    else:
        return jsonify({"Links": "/sync"})


@db_api_v0.route('/tap/sync/', methods=['GET', 'POST'])
def sync_query():
    """Synchronously run a query.
    :return: A proper response object
    """
    query = request.args.get("query", request.form.get("query", None))
    if query:
        log.debug(query)
        try:
            engine = _get_engine()
            results = []
            helpers = []
            rows = engine.execute(text(query))
            curs = rows.cursor

            for row in rows:
                # If this is the first row, build column definitions
                # (use raw values to help)
                if not helpers:
                    for desc, flags, val in zip(curs.description,
                                                curs.description_flags, row):
                        helpers.append(MySQLFieldHelper(desc, flags, val))

                # Not streaming...
                results.append([helper.check_value(val) for helper, val in zip(helpers, row)])

            status_code = OK
            elements = []
            for helper in helpers:
                field = dict(name=helper.name, datatype=helper.datatype)
                if helper.xtype:
                    field["xtype"] = helper.xtype
                elements.append(field)

            response = _result(dict(metadata=dict(elements=elements), data=results))
        except SQLAlchemyError as e:
            log.debug("Encountered an error processing request: '%s'" %
                    str(e))
            response = _error(type(e).__name__, str(e))
            status_code = INTERNAL_SERVER_ERROR
        return _response(response, status_code)
    else:
        return jsonify({"Info": "Listing queries is not implemented"})


@event.listens_for(Engine, "handle_error")
def handle_qserv_exception(context):
    conn = context.connection.connection
    if hasattr(conn, "error") and context.original_exception.args[0] == -1:
        # Handle Qserv Errors where we return error codes above those
        # identified by the MySQLdb driver.
        # The MySQL driver, by default, returns a "whack" error code
        # if this is the case with error == -1.
        from _mysql_exceptions import InterfaceError as MysqlIError
        old_exc = context.sqlalchemy_exception
        orig = MysqlIError(conn.errno(), conn.error())
        return InterfaceError(old_exc.statement, old_exc.params,
                              orig, old_exc.connection_invalidated)
    pass


def _get_engine():
    # Look for a dbserv-specific config URL, otherwise use default engine.
    db_engine = current_app.config.get("dax.dbserv.db.engine", None)
    if not db_engine:
        db_url = current_app.config.get("dax.dbserv.db.url", None)
        if db_url:
            pool_size = current_app.config.get("dax.dbserv.db.pool_size", 10)
            db_engine = create_engine(db_url, pool_size=pool_size)
        else:
            db_engine = current_app.config["default_engine"]
        current_app.config["dax.dbserv.db.engine"] = db_engine
    return db_engine


def _error(exception, message):
    return dict(error=exception, message=message)


def _result(table):
    return dict(result=dict(table=table))


votable_mappings = {
    "text": "unicodeChar",
    "binary": "unsignedByte"
}


def _response(response, status_code):
    fmt = request.accept_mimetypes.best_match(['application/json', 'text/html',
                                               'application/x-votable+xml'])
    if fmt == 'text/html':
        response = render_response(response=response, status_code=status_code)
    elif fmt == 'application/x-votable+xml':
        response = render_template('votable.xml.j2',
                                   result=response["result"],
                                   mappings=votable_mappings)
    else:
        response = jsonify(response)
    return make_response(response, status_code)
