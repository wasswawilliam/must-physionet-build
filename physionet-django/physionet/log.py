from copy import copy
from pythonjsonlogger import jsonlogger
import logging

from django.views import debug
from django.utils import log
from django.conf import settings
from django import template

# Below is based on django/views/templates/technical_500.txt.
#  - Values in POST are replaced with stars
#  - Values in FILES are replaced with stars
#  - Values in COOKIES are replaced with stars
#  - Values in META are replaced with stars
#  - Contents of the settings module are omitted entirely

TECHNICAL_500_TEXT_TEMPLATE = """
{% firstof exception_type 'Report' %}{% if request %} at {{ request.path_info }}{% endif %}
{% firstof exception_value 'No exception message supplied' %}
{% if request %}
Request Method: {{ request.META.REQUEST_METHOD }}
Request URL: {{ request.get_raw_uri }}{% endif %}
Django Version: {{ django_version_info }}
Python Executable: {{ sys_executable }}
Python Version: {{ sys_version_info }}
Python Path: {{ sys_path }}
Server time: {{server_time|date:"r"}}
Installed Applications:
{{ settings.INSTALLED_APPS|pprint }}
Installed Middleware:
{{ settings.MIDDLEWARE|pprint }}
{% if template_does_not_exist %}Template loader postmortem
{% if postmortem %}Django tried loading these templates, in this order:
{% for entry in postmortem %}
Using engine {{ entry.backend.name }}:
{% if entry.tried %}{% for attempt in entry.tried %}    * {{ attempt.0.loader_name }}: {{ attempt.0.name }} ({{ attempt.1 }})
{% endfor %}{% else %}    This engine did not provide a list of tried templates.
{% endif %}{% endfor %}
{% else %}No templates were found because your 'TEMPLATES' setting is not configured.
{% endif %}
{% endif %}{% if template_info %}
Template error:
In template {{ template_info.name }}, error at line {{ template_info.line }}
   {{ template_info.message }}
{% for source_line in template_info.source_lines %}{% if source_line.0 == template_info.line %}   {{ source_line.0 }} : {{ template_info.before }} {{ template_info.during }} {{ template_info.after }}{% else %}   {{ source_line.0 }} : {{ source_line.1 }}{% endif %}{% endfor %}{% endif %}{% if frames %}

Traceback:
{% for frame in frames %}{% ifchanged frame.exc_cause %}{% if frame.exc_cause %}
{% if frame.exc_cause_explicit %}The above exception ({{ frame.exc_cause }}) was the direct cause of the following exception:{% else %}During handling of the above exception ({{ frame.exc_cause }}), another exception occurred:{% endif %}
{% endif %}{% endifchanged %}
File "{{ frame.filename }}" in {{ frame.function }}
{% if frame.context_line %}  {{ frame.lineno }}. {{ frame.context_line }}{% endif %}
{% endfor %}
{% if exception_type %}Exception Type: {{ exception_type }}{% if request %} at {{ request.path_info }}{% endif %}
{% if exception_value %}Exception Value: {{ exception_value }}{% endif %}{% endif %}{% endif %}
{% if request %}Request information:
{% if user_str %}USER: {{ user_str }}{% endif %}

GET:{% for k, v in request_GET_items %}
{{ k }} = {{ v|stringformat:"r" }}{% empty %} No GET data{% endfor %}

POST:{% for k, v in filtered_POST_items %}
{{ k }} = '********************'{% empty %} No POST data{% endfor %}

FILES:{% for k, v in request_FILES_items %}
{{ k }} = '********************'{% empty %} No FILES data{% endfor %}

COOKIES:{% for k, v in request_COOKIES_items %}
{{ k }} = '********************'{% empty %} No cookie data{% endfor %}

META:
HTTP_USER_AGENT = {{ request.META.HTTP_USER_AGENT|stringformat:"r" }}
REMOTE_ADDR = {{ request.META.REMOTE_ADDR|stringformat:"r" }}
{% else %}Request data not supplied
{% endif %}
Settings:
Using settings module {{ settings.SETTINGS_MODULE }}

{% if not is_email %}
You're seeing this error because you have DEBUG = True in your
Django settings file. Change that to False, and Django will
display a standard page generated by the handler for this status code.
{% endif %}
"""


class ExceptionReporter(debug.ExceptionReporter):
    """
    An intermediate object used in constructing error messages.

    This class is equivalent to the built-in
    django.views.debug.ExceptionReporter, except that it omits most of
    the potentially sensitive information from the report.  It does
    not support generating an HTML report.
    """

    def get_traceback_text(self):
        t = debug.DEBUG_ENGINE.from_string(TECHNICAL_500_TEXT_TEMPLATE)
        c = template.Context(self.get_traceback_data(),
                             autoescape=False, use_l10n=False)
        return t.render(c)

    def get_traceback_html(self):
        return None


class SaferAdminEmailHandler(log.AdminEmailHandler):
    """
    Exception log handler that emails error messages to site admins.

    This class is equivalent to the built-in
    django.utils.log.AdminEmailHandler, except that it omits most of
    the potentially sensitive information from the report.  It does
    not support generating an HTML report.
    """

    # Below is a copy of django.utils.log.AdminEmailHandler.emit.
    # There are no changes to this function; it is simply redefined
    # here in order to use the custom ExceptionReporter class defined
    # above.

    def emit(self, record):
        try:
            request = record.request
            subject = '%s (%s IP): %s' % (
                record.levelname,
                ('internal' if request.META.get('REMOTE_ADDR') in settings.INTERNAL_IPS
                 else 'EXTERNAL'),
                record.getMessage()
            )
        except Exception:
            subject = '%s: %s' % (
                record.levelname,
                record.getMessage()
            )
            request = None
        subject = self.format_subject(subject)

        # Since we add a nicely formatted traceback on our own, create a copy
        # of the log record without the exception data.
        no_exc_record = copy(record)
        no_exc_record.exc_info = None
        no_exc_record.exc_text = None

        if record.exc_info:
            exc_info = record.exc_info
        else:
            exc_info = (None, record.getMessage(), None)

        reporter = ExceptionReporter(request, is_email=True, *exc_info)
        message = "%s\n\n%s" % (self.format(no_exc_record), reporter.get_traceback_text())
        html_message = reporter.get_traceback_html() if self.include_html else None
        self.send_mail(subject, message, fail_silently=True, html_message=html_message)


class VerboseStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            request = record.request
        except Exception:
            request = None

        # Since we add a nicely formatted traceback on our own, create a copy
        # of the log record without the exception data.
        no_exc_record = copy(record)
        no_exc_record.exc_info = None
        no_exc_record.exc_text = None

        if record.exc_info:
            exc_info = record.exc_info
        else:
            exc_info = (None, record.getMessage(), None)

        reporter = debug.ExceptionReporter(request, is_email=True, *exc_info)
        message = "%s\n\n%s" % (self.format(no_exc_record), reporter.get_traceback_text())
        self.stream.write(message)


class UwsgiJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(UwsgiJsonFormatter, self).add_fields(log_record, record, message_dict)
        log_record['source'] = 'django'
        log_record['level'] = log_record.pop('levelname')
        log_record['time'] = int(log_record.pop('created'))
        if log_record['sinfo'] is None:
            log_record.pop('sinfo')
