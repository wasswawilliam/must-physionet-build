"""
Module for generating notifications
"""
from email.utils import formataddr
from urllib import parse

from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMessage, mail_admins, send_mail
from django.template import defaultfilters, loader
from django.utils import timezone
from project.models import DataAccessRequest, License

RESPONSE_ACTIONS = {0:'rejected', 1:'accepted'}


def mailto_url(*recipients, **params):
    """
    Generate a 'mailto:' URL.

    The recipient address(es) are specified as positional arguments.
    Additional header fields (such as 'subject') and the special
    pseudo-header 'body' may be specified as keyword arguments.

    Note that RFC 6068 requires each recipient to be a simple address
    ("root@example.org"), while the older RFC 2368 permits the full
    RFC 822 mailbox syntax ("Root <root@example.org>").  Many, but not
    all, clients will accept the latter syntax.

    >>> mailto_url('alice@example.com', 'bob@example.com')
    'mailto:alice@example.com,bob@example.com'

    >>> mailto_url('fred&wilma@example.org', subject='Hello world')
    'mailto:fred%26wilma@example.org?subject=Hello%20world'
    """
    encoded_addrs = (parse.quote(addr, safe='@') for addr in recipients)
    url = 'mailto:' + ','.join(encoded_addrs)
    if params:
        url += '?' + parse.urlencode(params, quote_via=parse.quote)
    return url


def send_contact_message(contact_form):
    """
    Send a message to the contact email
    """
    subject = contact_form.cleaned_data['subject']
    body = contact_form.cleaned_data['message']
    mail_from = formataddr((contact_form.cleaned_data['name'],
        contact_form.cleaned_data['email']))
    message = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,  # envelope sender
        to=[settings.CONTACT_EMAIL],
        headers={
            'From': mail_from,
            'Sender': settings.DEFAULT_FROM_EMAIL
        })
    message.send(fail_silently=False)


# ---------- Project App ---------- #

def get_url_prefix(request):
    """
    Return a URL protocol and host, such as 'https://example.com'.

    django.contrib.sites.shortcuts is used to look up a "canonical"
    hostname, if one is defined.
    """
    site = get_current_site(request)
    if request and not request.is_secure():
        return 'http://' + site.domain
    else:
        return 'https://' + site.domain


def email_signature():
    """
    Gets the signature for the emails
    """
    signature = ("Regards,\n\n"
        "The PhysioNet Team,\n"
        "MIT Laboratory for Computational Physiology,\n"
        "Institute for Medical Engineering and Science,\n"
        "MIT, E25-505 77 Massachusetts Ave. Cambridge, MA 02139"
        )

    return signature

def email_project_info(project):
    """
    Header for the email. e.g. Project ID, Project title, Submitting Author.
    """
    header = ("Project title: {}\n"
        "Submission ID: {}\n"
        "Submitting author: {}"
        ).format(project.title, project.slug, project.submitting_author())

    return header

def email_footer():
    """
    Footer for the email. e.g. for privacy policy, link to update profile, etc.
    """
    footer = ""

    return footer

def invitation_notify(request, invite_author_form, target_email):
    """
    Notify someone when they are invited to author a project
    """
    inviter = invite_author_form.inviter
    project = invite_author_form.project
    subject = 'Invitation to author project: {}'.format(project.title)
    email_context = {
        'inviter_name': inviter.get_full_name(),
        'inviter_email': inviter.email,
        'project': project,
        'domain': get_current_site(request),
        'url_prefix': get_url_prefix(request),
        'signature': email_signature(),
        'project_info': email_project_info(project),
        'footer': email_footer(),
        'target_email': target_email
    }

    body = loader.render_to_string('notification/email/invite_author.html',
                                    email_context)

    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
                  [target_email], fail_silently=False)

def invitation_response_notify(invitation, affected_emails):
    """
    Notify the submitting author when an invitation to join a project
    is processed.
    """
    response = RESPONSE_ACTIONS[invitation.response]
    project = invitation.project

    subject = 'Authorship invitation {} for project: {}'.format(response,
                                                                project.title)
    email, name = project.author_contact_info(only_submitting=True)
    email_context = {
        'name': name,
        'project': project,
        'response': response,
        'signature': email_signature(),
        'project_info': email_project_info(project),
        'footer': email_footer()
    }

    # Send an email for each email belonging to the accepting user
    for author_email in affected_emails:
        email_context['author_email'] = author_email
        body = loader.render_to_string(
            'notification/email/author_response.html', email_context)

        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
                  [email], fail_silently=False)

def submit_notify(project):
    """
    Notify authors when a project is submitted
    """
    subject = 'Submission of project: {}'.format(project.title)
    email_context = {
        'project': project,
        'signature': email_signature(),
        'project_info': email_project_info(project),
        'footer': email_footer()
    }

    for email, name in project.author_contact_info():
        email_context['name'] = name
        body = loader.render_to_string(
            'notification/email/submit_notify.html', email_context)

        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
                  [email], fail_silently=False)

    # notify editorial team
    if project.core_project.publishedprojects.exists():
        subject = 'A new version has been submitted: {0}'.format(project.title)
    else:
        subject = 'A new project has been submitted: {0}'.format(project.title)
    email_context['name'] = "Colleague"
    body = loader.render_to_string(
        'notification/email/submit_notify_team.html', email_context)

    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
          [settings.CONTACT_EMAIL], fail_silently=False)


def resubmit_notify(project, comments):
    """
    Notify authors and the editor when a project is resubmitted
    """
    subject = 'Resubmission of project: {}'.format(project.title)
    email_context = {
        'project': project,
        'signature': email_signature(),
        'project_info': email_project_info(project),
        'footer': email_footer()
    }

    for email, name in project.author_contact_info():
        email_context['name'] = name
        body = loader.render_to_string(
            'notification/email/resubmit_notify.html', email_context)

        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
                          [email], fail_silently=False)

    # notify editorial team
    email_context['name'] = project.editor.get_full_name()
    email_context['author_comments'] = comments
    body = loader.render_to_string(
        'notification/email/resubmit_notify_editor.html', email_context)

    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
              [project.editor.email], fail_silently=False)

# ---------- Console App ---------- #

def assign_editor_notify(project):
    """
    Notify authors when an editor is assigned
    """
    subject = 'Editor assigned to submission of project: {0}'.format(
        project.title)

    for email, name in project.author_contact_info():
        body = loader.render_to_string(
            'notification/email/assign_editor_notify.html', {
                'name': name,
                'project': project,
                'editor': project.editor,
                'signature': email_signature(),
                'project_info': email_project_info(project),
                'footer': email_footer()
            })

        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
                  [email], fail_silently=False)


def editor_notify_new_project(project, assigner, reassigned=False):
    """
    Notify authors when an editor is assigned
    """
    subject = 'Assigned new project to review as editor ({0})'.format(
        project.title)

    body = loader.render_to_string(
        'notification/email/editor_notify_new_project.html', {
            'project': project,
            'editor': project.editor.get_full_name(),
            'signature': email_signature(),
            'user': assigner.get_full_name(),
            'project_info': email_project_info(project),
            'footer': email_footer()
        })
    if reassigned:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
                  [project.editor.email, assigner.email], fail_silently=False)
    else:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
                  [project.editor.email], fail_silently=False)


def edit_decision_notify(request, project, edit_log, reminder=False):
    """
    Notify authors when an editor makes a decision
    """
    # Reject
    if edit_log.decision == 0:
        subject = 'Submission rejected for project {}'.format(project.title)
        template = 'notification/email/reject_submission_notify.html'
    # Resubmit with revisions
    elif edit_log.decision == 1:
        subject = 'Revisions requested for project {}'.format(project.title)
        template = 'notification/email/revise_submission_notify.html'
    # Accept
    else:
        subject = 'Submission accepted for project: {}'.format(project.title)
        template = 'notification/email/accept_submission_notify.html'
    # Prepend reminder to the subject if needed
    if reminder:
        subject = "Reminder - {}".format(subject)

    for email, name in project.author_contact_info():
        body = loader.render_to_string(template, {
            'name': name,
            'project': project,
            'edit_log': edit_log,
            'domain': get_current_site(request),
            'url_prefix': get_url_prefix(request),
            'signature': email_signature(),
            'project_info': email_project_info(project),
            'footer': email_footer()
        })

        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
                  [email], fail_silently=False)


def copyedit_complete_notify(request, project, copyedit_log, reminder=False):
    """
    Notify authors when the editor has finished copyediting
    """
    subject = 'Your approval needed to publish: {0}'.format(project.title)
    # Prepend reminder to the subject if needed
    if reminder:
        subject = "Reminder - {}".format(subject)

    for person in project.author_list():
        if not person.approval_datetime:
            body = loader.render_to_string(
                'notification/email/copyedit_complete_notify.html', {
                    'name': person.get_full_name(),
                    'project': project,
                    'copyedit_log': copyedit_log,
                    'domain': get_current_site(request),
                    'url_prefix': get_url_prefix(request),
                    'signature': email_signature(),
                    'project_info': email_project_info(project),
                    'footer': email_footer()
                })
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
                      [person.user.email], fail_silently=False)


def reopen_copyedit_notify(request, project):
    """
    Notify authors when an editor reopens a project for copyediting
    """
    subject = 'Project reopened for copyediting: {0}'.format(project.title)

    for email, name in project.author_contact_info():
        body = loader.render_to_string(
            'notification/email/reopen_copyedit_notify.html', {
                'name': name,
                'project': project,
                'domain': get_current_site(request),
                'url_prefix': get_url_prefix(request),
                'signature': email_signature(),
                'project_info': email_project_info(project),
                'footer': email_footer()
            })

        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
                  [email], fail_silently=False)

def authors_approved_notify(request, project):
    """
    Notify ...
    """
    subject = 'All authors approved publication of project: {0}'.format(
        project.title)

    for email, name in project.author_contact_info():
        body = loader.render_to_string(
            'notification/email/authors_approved_notify.html', {
                'name': name,
                'project': project,
                'domain': get_current_site(request),
                'url_prefix': get_url_prefix(request),
                'signature': email_signature(),
                'project_info': email_project_info(project),
                'footer': email_footer()
            })

        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
                  [email], fail_silently=False)

def publish_notify(request, published_project):
    """
    Notify authors and administrators when a project is published
    """
    subject = 'Your project has been published: {0}'.format(
        published_project.title)

    content = {'published_project': published_project,
               'domain': get_current_site(request),
               'url_prefix': get_url_prefix(request),
               'signature': email_signature(),
               'project_info': email_project_info(published_project),
               'footer': email_footer()}

    for email, name in published_project.author_contact_info():
        content['name'] = name
        body = loader.render_to_string(
            'notification/email/publish_notify.html', content)
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
                  [email], fail_silently=False)

    subject = 'A new project has been published: {0}'.format(
        published_project.title)
    content['name'] = "Colleague"
    body = loader.render_to_string(
        'notification/email/publish_notify_team.html', content)

    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
          [settings.CONTACT_EMAIL], fail_silently=False)


def storage_request_notify(request, project):
    """
    Notify administrators when a storage request is received
    """
    subject = 'Storage request received: {0}'.format(
        project.title)

    content = {'project': project,
               'domain': get_current_site(request),
               'url_prefix': get_url_prefix(request),
               'signature': email_signature(),
               'project_info': email_project_info(project),
               'footer': email_footer()}

    content['name'] = "Colleague"
    body = loader.render_to_string(
        'notification/email/storage_request_notify_team.html', content)

    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
              [settings.CONTACT_EMAIL], fail_silently=False)


def storage_response_notify(storage_request):
    """
    Notify submitting author when storage request is processed
    """
    project = storage_request.project
    response = RESPONSE_ACTIONS[storage_request.response]
    subject = 'Storage request {0} for project: {1}'.format(response,
        project.title)
    email, name = project.author_contact_info(only_submitting=True)
    body = loader.render_to_string(
        'notification/email/storage_response_notify.html', {
            'name': name,
            'project': project,
            'response': response,
            'allowance': storage_request.request_allowance,
            'response_message': storage_request.response_message,
            'signature': email_signature(),
            'project_info': email_project_info(project),
            'footer': email_footer()
        })

    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
              [email], fail_silently=False)


def contact_applicant(request, application, comments):
    """
    Request applicant feedback regarding their credentialing application
    """
    applicant_name = ' '.join([application.first_names, application.last_name])
    subject = 'Feedback regarding your PhysioNet credentialing application'
    respond_email = settings.CREDENTIAL_EMAIL
    body = loader.render_to_string(
        'notification/email/contact_applicant.html', {
            'application': application,
            'applicant_name': applicant_name,
            'comments': comments,
            'url_prefix': get_url_prefix(request),
            'signature': email_signature()
        })

    send_mail(subject, body, respond_email, [application.user.email],
              fail_silently=False)


def contact_reference(request, application, send=True, wordwrap=True,
                      subject="", body=""):
    """
    Request verification from a credentialing applicant's reference.

    Args:
        application : CredentialApplication object.
        send : If True, send the email.
        wordwrap : If True, wraps body at 70 characters.
        subject : Subject line.
        body : Body text.

    Returns:
        dict : email name, subject, body
    """
    applicant_name = ' '.join([application.first_names, application.last_name])

    if not subject:
        subject = 'Reference requested for {}'.format(
            applicant_name)
    if not body:
        body = loader.render_to_string(
            'notification/email/contact_reference.html', {
                'application': application,
                'applicant_name': applicant_name,
                'domain': get_current_site(request),
                'url_prefix': get_url_prefix(request),
                'signature': email_signature(),
                'footer': email_footer()
            })

    if wordwrap:
        body = defaultfilters.wordwrap(body, 70)

    if send:
        send_mail(subject, body, settings.CREDENTIAL_EMAIL,
                  [application.reference_email], fail_silently=False)

    return {"subject": subject, "body": body}


def contact_supervisor(request, application):
    """
    Request verification from a credentialing applicant's reference
    """
    applicant_name = ' '.join([application.first_names, application.last_name])
    subject = 'Please verify {} for PhysioNet credentialing'.format(
        applicant_name)
    body = loader.render_to_string(
        'notification/email/contact_supervisor.html', {
            'application': application,
            'applicant_name': applicant_name,
            'domain': get_current_site(request),
            'url_prefix': get_url_prefix(request),
            'signature': email_signature(),
            'footer': email_footer()
        })

    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
              [application.reference_email], fail_silently=False)

def mailto_reference(request, application):
    """
    Request verification from a credentialing applicant's reference
    """
    applicant_name = application.get_full_name()
    subject = '{} -- PhysioNet clinical database access request'.format(
        applicant_name)
    body = loader.render_to_string(
        'notification/email/mailto_contact_reference.html', {
            'application': application,
            'applicant_name': applicant_name,
            'domain': get_current_site(request),
            'url_prefix': get_url_prefix(request),
            'signature': email_signature(),
            'footer': email_footer()
        })

    # rm comma to handle mailto issue with comma and special char.
    # ref https://github.com/MIT-LCP/physionet-build/issues/1028
    to = formataddr((application.reference_name.replace(',', ''),
                     application.reference_email))
    bcc = 'credential-reference+{0}@{1}'.format(
        application.id, get_current_site(request))
    return mailto_url(to, subject=subject, bcc=bcc, body=body)


def mailto_supervisor(request, application):
    """
    Request verification from a credentialing applicant's reference
    """
    applicant_name = application.get_full_name()
    subject = '{} -- PhysioNet clinical database access request'.format(
        applicant_name)
    body = loader.render_to_string(
        'notification/email/mailto_contact_supervisor.html', {
            'application': application,
            'applicant_name': applicant_name,
            'domain': get_current_site(request),
            'url_prefix': get_url_prefix(request),
            'signature': email_signature(),
            'footer': email_footer()
        })

    # rm comma to handle mailto issue with comma and special char.
    # ref https://github.com/MIT-LCP/physionet-build/issues/1028
    to = formataddr((application.reference_name.replace(',', ''),
                     application.reference_email))
    bcc = 'credential-reference+{0}@{1}'.format(
        application.id, get_current_site(request))
    return mailto_url(to, subject=subject, bcc=bcc, body=body)


def mailto_process_credential_complete(request, application, comments=True):
    """
    Notify user of credentialing decision
    """
    applicant_name = application.get_full_name()
    subject = 'PhysioNet clinical database access request for {}'.format(applicant_name)
    dua = License.objects.get(slug='physionet-credentialed-health-data-license-150')
    body = loader.render_to_string(
        'notification/email/mailto_contact_applicant.html', {
            'application': application,
            'dua': dua.dua_text_content()
        }).replace('\n', '\n> ')

    if comments:
        body = 'Dear {0},\n\n{1}\n\n{2}'.format(application.first_names,
          application.responder_comments, body)
    else:
        body = 'Dear {0},\n\n{1}'.format(application.first_names, body)

    # rm comma to handle mailto issue with comma and special char.
    # Ref https://github.com/MIT-LCP/physionet-build/issues/1028
    to = formataddr((application.get_full_name().replace(',', ''),
                     application.user.email))
    bcc = 'credential-reference+{0}@{1}'.format(
        application.id, get_current_site(request))
    return mailto_url(to, subject=subject, bcc=bcc, body=body)


def mailto_administrators(project, error):
    """
    Request verification from a credentialing applicant's reference
    """
    subject = 'Error sending files to GCP for {}'.format(project.slug)
    body = loader.render_to_string(
        'notification/email/contact_administrators.html', {
            'project': project,
            'error': error,
            'signature': email_signature(),
            'footer': email_footer()
        })

    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
              [settings.CONTACT_EMAIL], fail_silently=False)

def process_credential_complete(request, application, comments=True):
    """
    Notify user of credentialing decision
    """
    applicant_name = application.get_full_name()
    response = 'rejected' if application.status == 1 else 'accepted'
    subject = 'Your application for PhysioNet credentialing'
    body = loader.render_to_string(
        'notification/email/process_credential_complete.html', {
            'application': application,
            'applicant_name': applicant_name,
            'domain': get_current_site(request),
            'url_prefix': get_url_prefix(request),
            'comments': comments,
            'signature': email_signature(),
            'footer': email_footer()
        })

    message = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[application.user.email],
        bcc=[settings.CREDENTIAL_EMAIL]
        )
    message.send(fail_silently=False)

def credential_application_request(request, application):
    """
    Notify user of credentialing decision
    """
    applicant_name = application.get_full_name()
    subject = 'PhysioNet credentialing application notification'
    dua = License.objects.get(slug='physionet-credentialed-health-data-license-150')
    body = loader.render_to_string(
        'notification/email/notify_credential_request.html', {
            'application': application,
            'applicant_name': applicant_name,
            'domain': get_current_site(request),
            'url_prefix': get_url_prefix(request),
            'dua': dua.dua_text_content(),
            'signature': email_signature(),
            'footer': email_footer()
        })

    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
              [application.user.email], fail_silently=False)

def notify_gcp_access_request(data_access, user, project):
    """
    Notify user of GCP access
    """
    subject = 'PhysioNet Google Cloud Platform BigQuery access'
    email = user.cloud_information.gcp_email.email
    if data_access.platform == 3:
        subject = 'PhysioNet Google Cloud Platform storage read access'
    body = loader.render_to_string(
        'notification/email/notify_gcp_access_request.html', {
            'signature': email_signature(),
            'data_access': data_access,
            'user': user,
            'project': project,
            'footer': email_footer()
        })

    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
              [email], fail_silently=False)

def notify_aws_access_request(user, project, data_access, successful):
    subject = 'PhysioNet Amazon Web Service storage access'
    body = loader.render_to_string(
        'notification/email/notify_aws_access_request.html', {
            'user': user,
            'project': project,
            'successful': successful,
            'contact_email': settings.CONTACT_EMAIL,
            'signature': email_signature(),
            'footer': email_footer(),
            'data_access': data_access
        })

    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
              [user.email], fail_silently=False)


def notify_owner_data_access_request(users, data_access_request,
                                     request_protocol, request_host):
    subject = "PhysioNet New Data Access Request"

    for user in users:
        body = loader.render_to_string(
            'notification/email/notify_owner_data_access_request.html', {
                'user': user,
                'data_access_request': data_access_request,
                'signature': email_signature(),
                'footer': email_footer(),
                'request_host': request_host,
                'request_protocol': request_protocol
            })

        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
                  [user.email],
                  fail_silently=False)


def confirm_user_data_access_request(data_access_request, request_protocol,
                                     request_host):
    subject = "PhysioNet Data Access Request"

    due_date = timezone.now() + timezone.timedelta(
        days=DataAccessRequest.DATA_ACCESS_REQUESTS_DAY_LIMIT)

    body = loader.render_to_string(
        'notification/email/confirm_user_data_access_request.html', {
            'data_access_request': data_access_request,
            'signature': email_signature(),
            'footer': email_footer(),
            'request_host': request_host,
            'request_protocol': request_protocol,
            'due_date': due_date
        })

    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
              [data_access_request.requester.email],
              fail_silently=False)


def notify_user_data_access_request(data_access_request, request_protocol,
                                    request_host):
    subject = "PhysioNet Data Access Request Decision"

    body = loader.render_to_string(
        'notification/email/notify_user_data_access_request.html', {
            'data_access_request': data_access_request,
            'signature': email_signature(),
            'footer': email_footer(),
            'request_host': request_host,
            'request_protocol': request_protocol,
        })

    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
              [data_access_request.requester.email],
              fail_silently=False)


def notify_user_invited_managing_requests(reviewer_invitation, request_protocol, request_host):
    subject = "PhysioNet Invitation to Review Requests"

    body = loader.render_to_string(
        'notification/email/notify_user_invited_managing_requests.html', {
            'invitation': reviewer_invitation,
            'signature': email_signature(),
            'footer': email_footer(),
            'request_host': request_host,
            'request_protocol': request_protocol,
        })

    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
              [reviewer_invitation.reviewer.email],
              fail_silently=False)


def notify_owner_data_access_review_withdrawal(reviewer_invitation):
    subject = "PhysioNet Data Request Reviewer Withdrawal"

    project = reviewer_invitation.project
    for user in set([project.submitting_author().user, project.corresponding_author().user]):
        body = loader.render_to_string(
            'notification/email/notify_owner_data_access_review_withdrawal.html', {
                'owner': user,
                'user': reviewer_invitation.reviewer,
                'project': project,
                'signature': email_signature(),
                'footer': email_footer(),
            })

        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
                  [user.email],
                  fail_silently=False)


def task_failed_notify(name, attempts, last_error, date_time, task_name, task_params):
    """
    Notify when a task has failed and not rescheduled
    """
    body = loader.render_to_string(
        'notification/email/notify_failed_task.html', {
            'name': name,
            'attempts': attempts,
            'last_error': last_error,
            'date_time': date_time.strftime("%Y-%m-%d %H:%M:%S"),
            'task_name': task_name,
            'task_params': task_params,
            'signature': email_signature()
        })
    subject = name + " has failed"
    mail_admins(subject, body, settings.DEFAULT_FROM_EMAIL)


def task_rescheduled_notify(name, attempts, last_error, date_time, task_name, task_params):
    """
    Notify when a task has been rescheduled
    """
    body = loader.render_to_string(
        'notification/email/notify_rescheduled_task.html', {
            'name': name,
            'attempts': attempts,
            'last_error': last_error,
            'date_time': date_time.strftime("%Y-%m-%d %H:%M:%S"),
            'task_name': task_name,
            'task_params': task_params,
            'signature': email_signature()
        })
    subject = name + " has been rescheduled"
    mail_admins(subject, body, settings.DEFAULT_FROM_EMAIL)


def notify_account_registration(request, user, uidb64, token):
    """
    Send the registration email.
    """
    # Send an email with the activation link
    subject = "PhysioNet Account Activation"
    context = {
        'name': user.get_full_name(),
        'domain': get_current_site(request),
        'url_prefix': get_url_prefix(request),
        'uidb64': uidb64,
        'token': token
    }
    body = loader.render_to_string('user/email/register_email.html', context)
    # Not resend the email if there was an integrity error
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
              [user.email], fail_silently=False)

def notify_sso_account_registration(request, user, uidb64, token):
    """
    Send the SSO email confirmation email
    """

    # Send an email with the activation link
    subject = "PhysioNet Account Activation"
    context = {
        'name': user.get_full_name(),
        'domain': get_current_site(request),
        'url_prefix': get_url_prefix(request),
        'uidb64': uidb64,
        'token': token,
    }
    body = loader.render_to_string('user/email/sso_register_email.html', context)
    # Not resend the email if there was an integrity error
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
