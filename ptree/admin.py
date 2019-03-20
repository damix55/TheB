from django.contrib import admin
from django.utils.html import format_html
from django.http import HttpResponseRedirect

from mptt.admin import MPTTModelAdmin

from .models import *
from .forms import *
from scripts import github

class MantainerAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['username', 'profile']
        else:
            return []

    def profile(self, obj):
        profile = obj.get_profile()
        username = obj.username
        html = '<a target="_blank" href="' + profile + '">' + profile + '</a>'
        return format_html(html)



class ProjectAdmin(MPTTModelAdmin):
    mptt_level_indent = 20

    #############################################  Tree view  #############################################
    list_display = ('title_state',)
    list_display_links = ('title_state',)
    list_filter = ['state']

    # The title is gray if the project is in pending state
    def title_state(self, instance):
        color = ''
        sync = ''

        if(instance.state=='pending'):
            color = 'color: #CCC'

        # # Add a tick or a cross if it is synched with GitHub or not
        # if(instance.is_synched()):
        #     sync = '<span style="color: green">✔</span>'
        # else:
        #     sync = '<span style="color: red">✘</span>'

        return format_html(
            '<div style="text-indent:{}px;{}">{}</div>',
            instance._mpttfield('level') * self.mptt_level_indent,
            color,
            instance.name
        )
    title_state.short_description = 'Name'


    ############################################  Change view  ############################################
    change_form_template = 'change_form.html'
    form = ProjectForm

    # readonly_fields only when editing, not when creating an object
    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['parent', 'children', 'title', 'state', 'get_branch', 'mantainers_hierarchy', 'payments', 'is_synched', 'url']
        else:
            return []

    # Populate admin change_form with field loaded from GitHub
    def get_form(self, request, obj=None, **kwargs):
        form = super(ProjectAdmin, self).get_form(request, obj, **kwargs)
        if obj is not None:
            data = obj.get_json()
            form.base_fields['description'].initial = obj.description
            form.base_fields['weight'].initial = data.get('weight')
            form.base_fields['threshold'].initial = data.get('threshold')
            form.base_fields['limit'].initial = data.get('limit')
            form.base_fields['expiration_time'].initial = data.get('expiration_time')
        else:
            form.base_fields['description'].initial = ''
            form.base_fields['weight'].initial = None
            form.base_fields['threshold'].initial = None
            form.base_fields['limit'].initial = None
            form.base_fields['expiration_time'].initial = None
            try:
                form.base_fields['parent'].initial = request.GET['parent']
            except:
                pass

        return form

    def children(self, obj):
        children = obj.get_children()
        html = ', '.join(['<a href="../../' + c.title + '">' + c.name + '</a>' for c in children])
        return format_html(html)

    def get_branch(self, obj):
        branch = obj.get_branch()
        html = '<a target="_blank" href="' + github.repo_url + '/tree/' + branch + '">' + branch + '</a>'
        return format_html(html)
    get_branch.short_description = 'Branch'

    def mantainers_hierarchy(self, obj):
        html = '<table><thead><tr><th>Name</th><th>Rank</th></tr></thead><tbody>'
        for m, r in obj.mantainers_hierarchy().items():
            html += '<tr><td><a target="_blank" href="../../../mantainer/' + m + '">' + m + '</a></td><td>' + str(r) + '</td></tr>'
        html += '</tbody></table>'
        return format_html(html)

    def payments(self, obj):
        html = '<table><thead><tr><th>Amount</th><th>Donor</th><th>Date</th></tr></thead><tbody>'
        payments = obj.get_payments()
        if payments is not None:
            for p in payments:
                if p.get('donor') is None:
                    donor = '<i>Anonymous</i>'
                else:
                    donor = p.get('donor')
                    donor = '<a target="_blank" href="https://github.com/' + donor + '">' + donor + '</a>'
                html += '<tr><td>' + str(p.get('amount')) + '</td><td>' + donor + '</td><td>' + p.get('date') + '</td></tr>'

        html += '</tbody></table>'
        return format_html(html)

    def is_synched(self, obj):
        if(obj.is_synched()):
            url = obj.github_url()
            sync = '<span style="color: green">✔</span> <a target="_blank" href="' + url + '">' + url + '</a>'
        else:
            sync = '<span style="color: red">✘</span>'
        return format_html(sync)
    is_synched.short_description = 'GitHub synchronization'

    def url(self, obj):
        url = obj.get_url()
        html = '<a target="_blank" href="' + url + '">' + url + '</a>'
        return format_html(html)
    url.short_description = 'URL'

    def response_change(self, request, obj):
        # NOT ALWAYS WORKING - possible fix: disable save
        # Approve button in 'change' view
        if "_activate" in request.POST:
            pr = github.get_pulls(head=obj.get_branch())[0]
            obj.activate(pr)
            self.message_user(request, 'Project approved')
            return HttpResponseRedirect('.')

        if "_addchildren" in request.POST:
            return HttpResponseRedirect('../../add/?parent=' + obj.title)

        return super().response_change(request, obj)


    def save_model(self, request, obj, form, change):
        old_path = obj.get_path()
        super(ProjectAdmin, self).save_model(request, obj, form, change)

        # NEEDS CHECK
        # Checks if the path changes and eventually moves the files
        if old_path!=obj.get_path() and old_path is not None:
            github.move(old_path, obj.get_path(), obj.get_branch(), 'Moved project ' + obj.name)

        obj.write_to_github(form, 'Updated project ' + obj.name)

        #Updates pull request
        if(obj.state=='pending'):
            pr = github.get_pulls(head=obj.get_branch())[0]
            github.pull_edit(pr, title=obj.name, body=obj.description)


admin.site.register(Mantainer, MantainerAdmin)
admin.site.register(Project, ProjectAdmin)
