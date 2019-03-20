from .forms import ProjectFormUser, PayForm
from .models import *
from scripts import github

import hmac
from hashlib import sha1
import math

from django.shortcuts import render
from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden, HttpResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.encoding import force_bytes

import requests
from ipaddress import ip_address, ip_network

def home(request):
    return project(request, 'the-b')

def tree_view(request):
    return render(request, 'tree-view.html')

def project(request, project_name):
    try:
        project = Project.objects.get(pk=project_name)
    except:
        return HttpResponse('404')

    return render(request, 'project.html', {
        'project' : project,
        'data' : project.get_json(),
        'description' : project.description,
        'donors' : project.get_top_donors()
    })

def new_project(request, project_name):
    try:
        project = Project.objects.get(pk=project_name)
    except:
        return HttpResponse('404')

    if request.method == 'POST':
        form = ProjectFormUser(request.POST, parent=project)
        if form.is_valid():
            form.cleaned_data.update({'parent' : project})
            newproject = form.save()
            newproject.write_to_github(form, 'Created project ' + newproject.name)
            return HttpResponseRedirect('/project/' + newproject.title)

    else:
        form = ProjectFormUser(parent=project)

    return render(request, 'new-project.html', {
        'form': form,
        'project' : project
    })



def pay(request, project_name):
    try:
        project = Project.objects.get(pk=project_name)
    except:
        return HttpResponse('404')

    if request.method == 'POST':
        form = PayForm(request.POST)
        if form.is_valid():
            project.add_payments(form)
            return HttpResponseRedirect('/project/' + project.title)

    else:
        form = PayForm()

    return render(request, 'pay.html', {
        'form': form,
        'project' : project
    })



@require_POST
@csrf_exempt
def webhooks(request):
    # Verify if request came from GitHub
    forwarded_for = u'{}'.format(request.META.get('HTTP_X_FORWARDED_FOR'))
    client_ip_address = ip_address(forwarded_for)
    whitelist = requests.get('https://api.github.com/meta').json()['hooks']

    for valid_ip in whitelist:
        if client_ip_address in ip_network(valid_ip):
            break
    else:
        return HttpResponseForbidden('Permission denied.')

    # Verify the request signature
    header_signature = request.META.get('HTTP_X_HUB_SIGNATURE')
    if header_signature is None:
        return HttpResponseForbidden('Permission denied.')

    sha_name, signature = header_signature.split('=')
    if sha_name != 'sha1':
        return HttpResponseServerError('Operation not supported.', status=501)

    mac = hmac.new(force_bytes(settings.GITHUB_WEBHOOK_KEY), msg=force_bytes(request.body), digestmod=sha1)
    if not hmac.compare_digest(force_bytes(mac.hexdigest()), force_bytes(signature)):
        return HttpResponseForbidden('Permission denied.')

    # Process the GitHub events
    event = request.META.get('HTTP_X_GITHUB_EVENT')
    payload = json.loads(request.body)

    # Check if it is a closed pull request, delete the branch
    if event == 'pull_request' and payload.get('action') == 'closed':
        number = payload.get('pull_request').get('number')
        pr = github.get_pull(number)
        project = get_project_from_pr(pr)
        github.delete_branch(pr.head.ref)

        # Check if it is merged
        if payload.get('pull_request').get('merged'):
            project.state = 'active'
            project.save()
        # If not, delete the model in the database
        else:
            project.delete()

    # Check if it is a comment in a pull request
    elif event == 'issue_comment' and 'pull_request' in payload.get('issue'):
        number = payload.get('issue').get('number')
        pr = github.get_pull(number)
        project = get_project_from_pr(pr)
        first_rank_mantainers = len(project.get_mantainers_name())
        hierarchy = project.mantainers_hierarchy()
        comments = github.pull_get_issue_comments(pr)

        print(hierarchy)
        jud = judgment(hierarchy, comments, first_rank_mantainers)

        if(jud==1):
            project.activate(pr)

        elif(jud==-1):
            pass
            #TODO: delete

        return HttpResponse('ok')

    return HttpResponse(status=204)



#SOLUZIONE TEMPORANEA:
#  il total_score deve essere uguale almeno alla somma dei mantainer di rank 1
#  ogni mantainer ha un peso diverso in base a che grado ha nella gerarchia

# TODO: gerarchia parte da nodo sopra, non dallo stesso

def judgment(hierarchy, comments, first_rank_mantainers):
    total_mantainers = len(hierarchy)
    total_votes = 0
    total_score = 0

    for c in comments:
        if(c.body == "ACK" or c.body == "NACK"):
            user = c.user.login
            if user in hierarchy:
                total_votes += 1
                score = 1/math.exp(hierarchy[user])
                if(c.body == "ACK"):
                    total_score += score
                else:
                    total_score -= score

                hierarchy.pop(user)

    print("Score:         " + str(total_score))
    print("Minimum score: " + str(first_rank_mantainers))
    print("Votes:         " + str(total_votes))
    print("Mantainers:    " + str(total_mantainers))

    if(total_score>=first_rank_mantainers):
        print("PASSED!")
        return 1

    elif(-total_score>=first_rank_mantainers):
        print("DELETED!")
        return -1

    else:
        print("NOPE")
        return 0

# Get the project name from the path of the folder where project.json is
def get_project_from_pr(pr):
    for f in github.pull_get_files(pr):
        dir = f.filename.split('/')
        if dir[-1] == 'project.json':
            project_name = dir[-2]

    # Get the project object from the name
    return Project.objects.get(pk=project_name)
