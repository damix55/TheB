from django.db import models
from django.utils.text import slugify
from django.core.serializers.json import DjangoJSONEncoder
from scripts import github
from mptt.models import MPTTModel, TreeForeignKey
from datetime import datetime
import json
import re


class Mantainer(models.Model):
    username = models.SlugField(max_length=50, unique=True, primary_key=True)

    def get_profile(self):
        return 'https://github.com/' + self.username

    def __str__(self):
        return self.username

    def save(self, *args, **kwargs):
        super(Mantainer, self).save(*args, **kwargs)



class Project(MPTTModel):
    class Meta:
        verbose_name = 'Project'
        verbose_name_plural = 'Projects'

    class MPTTMeta:
        order_insertion_by = ['name']



    ###############################################################################################

    STATE = (
        ("pending", "Pending"),
        ("active", "Active")
    )
    name = models.CharField(max_length=50, unique=True)
    title = models.SlugField(max_length=50, unique=True, primary_key=True, editable=False)
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    state = models.CharField(max_length=20, choices=STATE, default="pending")
    mantainers = models.ManyToManyField(Mantainer)

    @property
    def description(self):
        return github.get_file(self.get_path()+'/description.md', self.get_branch()).decode('unicode_escape')

    @property
    def weight(self):
        try:
            return self.get_json().get('weight')
        except:
            return None

    @property
    def threshold(self):
        return self.get_json().get('threshold')

    @property
    def limit(self):
        return self.get_json().get('limit')

    @property
    def expiration_time(self):
        return self.get_json().get('expiration_time')



    ###############################################################################################

    def save(self, *args, **kwargs):
        if not self.title:
            slug = slugify(self.name)
            # Check if a project with this slug already exist, generates a new one
            while Project.objects.filter(pk=slug).exists():
                regex = re.search('[-]\d+$', slug)
                if regex:
                    old_number = regex.group()[1:]
                    new_number = str(int(old_number)+1)
                    slug = re.sub(old_number + '$', new_number, slug)
                else:
                    slug = slug + '-2'

            self.title = slug
        super(Project, self).save(*args, **kwargs)


    def delete(self, *args, **kwargs):
        if(self.is_synched()):
            if(self.state=='pending'):
                github.delete_branch(self.get_branch())
            else:
                github.delete_folder(self.get_path(), self.get_branch(), 'Deleted project ' + self.name)

        super(Project, self).delete(*args, **kwargs)


    def activate(self, pr):
        if(self.state=='pending'):
            github.pull_merge(pr, commit_message='', commit_title='Added project ' + self.name, merge_method='merge'
            #, sha=NotSet
            )
            self.state = 'active'
            self.save()



    ########################################### GETTERS ############################################

    def __str__(self):
        return self.name


    def get_path(self):
        try:
            ancestors = self.get_ancestors(ascending=False, include_self=True)
            path = ''
            for node in ancestors:
                path += node.title + '/'
            return path[:-1]                    # remove the last slash which is not necessary
        except:
            return self.title

    def get_branch(self):
        if(self.state=='pending'):
            return 'new-project-' + self.title
        else:
            return 'master'

    def get_mantainers_name(self):
        names = []
        for m in list(self.mantainers.all()):
            names.append(m.username)
        return names


    # Every mantainer of the current node (if not in pending) and ancestors gets a rank
    # based on the distance of the node they are mantainer of, for decision-making
    def mantainers_hierarchy(self):
        mantainers_hierarchy = {}
        if self.state == 'pending':
            rank = 0
        else:
            for m in self.get_mantainers_name():
                mantainers_hierarchy.update({m:0})
            rank = 1

        p = self
        while p.parent is not None:
            p = p.parent
            for m in p.get_mantainers_name():
                if m not in mantainers_hierarchy:
                    mantainers_hierarchy.update({m:rank})
            rank += 1
        return mantainers_hierarchy


    def is_synched(self):
        return github.path_exists(self.get_path()+'/project.json', self.get_branch())


    def get_json(self):
        return json.loads(github.get_file(self.get_path()+'/project.json', self.get_branch()))


    def get_payments(self):
        try:
            return json.loads(github.get_file(self.get_path()+'/payments.json', self.get_branch()))
        except:
            return None


    def get_total_payments(self, payments=None):
        if payments is None:
            payments = self.get_payments()

        if payments is not None:
            total = 0
            for p in payments:
                total += p.get('amount')
            return total

        return 0;


    def get_donors(self):
        payments = self.get_payments()
        donors = {}

        if payments is not None:
            for p in payments:
                donors[p.get('donor')] = donors.get(p.get('donor'), 0) + p.get('amount')

        return {k: v for k, v in sorted(donors.items(), key=lambda x: x[1], reverse=True) if k is not None}


    def get_top_donors(self):
        donors = self.get_donors()
        donors_list = list(donors.keys())
        return donors_list[:3]


    def github_url(self):
        return github.repo_url + '/tree/' + self.get_branch() + '/' + self.get_path()


    def get_url(self):
        return '/project/' + self.title


    ###############################################################################################

    def write_to_github(self, form, message):
        branch = self.get_branch()
        branch_exists = github.branch_exists(branch)

        # Create the branch if it doesn't exist
        if not branch_exists:
            github.create_branch(branch)

        # Generate the project.json
        path = self.get_path() + '/project.json'
        data = {
            'name' : self.name,
            'state' : self.state,
            'mantainers' : self.get_mantainers_name(),
            'weight' : int(form['weight'].value()),
        }

        threshold = form['threshold'].value()
        if threshold != '':
            data.update({'threshold' : int(threshold)})

        limit = form['limit'].value()
        if limit != '':
            data.update({'limit' : int(limit)})

        expiration_time = form['expiration_time'].value()
        if expiration_time != '':
            data.update({'expiration_time' : int(expiration_time)})

        json_data = json.dumps(data, indent=4) + '\n'
        github.write(path, json_data, message, branch)

        #Generate the description.md
        path = self.get_path() + '/description.md'
        github.write(path, form['description'].value(), message, branch)


        # Generate the pull request eventually
        if not branch_exists:
            github.create_pull(title=self.name, head=branch, base='master', body=self.description, maintainer_can_modify=True)


    def update_json(self, message, **kwargs):
        data = self.get_json()
        for k in kwargs:
            data.update({k : kwargs.get(k)})

        json_data = json.dumps(data, indent=4) + '\n'
        github.write(path, json_data, message, branch)


    def add_payments(self, form):
        branch = self.get_branch()
        path = self.get_path() + '/payments.json'
        data = {
            'amount' : int(form['amount'].value()),
            'date' : datetime.now(),
        }
        if form['donor'].value() != '':
            data.update({'donor' : form['donor'].value()})

        payments = self.get_payments()

        if payments is None:
            payments = []

        payments.append(data)

        json_data = json.dumps(payments, indent=4, cls=DjangoJSONEncoder) + '\n'
        github.write(path, json_data, 'Added new payment', branch)

        total = self.get_total_payments(payments)

        # if total >= self.threshold: #and *stato da decidere*
        #     #nuovo stato da decidere
        #     #nuova expiration?
        #     pass
