# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

import uuid

from django.conf import settings
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.db.models.signals import post_save

from clusters.models import Cluster
from experiments.signals import new_experiment, new_experiment_job, new_experiment_job_status
from libs.models import DiffModel
from spawner.utils.constants import JobLifeCycle, ExperimentLifeCycle


class Experiment(DiffModel):
    """A model that represents experiments."""

    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        null=False)
    cluster = models.ForeignKey(
        Cluster,
        related_name='experiments')
    project = models.ForeignKey(
        'projects.Project',
        related_name='experiments')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='experiments')
    name = models.CharField(
        max_length=256,
        blank=True,
        null=True,
        help_text='Name of the experiment')
    description = models.TextField(
        blank=True,
        null=True,
        help_text='Description of the experiment.')
    spec = models.ForeignKey(
        'projects.PolyaxonSpec',
        blank=True,
        null=True,
        related_name='experiments',
        help_text='The polyaxon_spec that generate this experiment.')
    config = JSONField(
        # TODO: should be validated by the Specification validator
        help_text='The compiled polyaxon with specific values for this experiment.')
    original_experiment = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        related_name='clones',
        help_text='The original experiment that was cloned from.')

    @property
    def last_job_statuses(self):
        """The statuses of the job in this experiment."""
        from libs.redis_db import RedisExperimentJobStatus

        statuses = []
        for job_uuid in self.jobs.object.values_list('uuid', flat=True):
            status = RedisExperimentJobStatus.get_status(job_uuid=job_uuid)
            statuses.append(status)
        return statuses

    @property
    def calculated_status(self):
        return ExperimentLifeCycle.jobs_status(self.last_job_statuses)

    @property
    def last_status(self):
        return self.status.last()

    @property
    def is_running(self):
        return ExperimentLifeCycle.is_running(self.last_status.status)

    @property
    def is_done(self):
        return ExperimentLifeCycle.is_done(self.last_status.status)

    @property
    def finished_at(self):
        status = self.status.filter(status__in=ExperimentLifeCycle.DONE_STATUS).first()
        if status:
            return status.created_at
        return None

    @property
    def started_at(self):
        status = self.status.filter(status=ExperimentLifeCycle.STARTING).first()
        if status:
            return status.created_at
        return None

    @property
    def is_clone(self):
        return self.original_experiment is not None

    @property
    def is_independent(self):
        """If the experiment belongs to a polyaxon_spec or is independently created."""
        return not self.spec


post_save.connect(new_experiment, sender=Experiment, dispatch_uid="experiment_saved")


class ExperimentStatus(models.Model):
    """A model that represents an experiment status at certain time."""
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        null=False)
    experiment = models.ForeignKey(Experiment, related_name='status')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    status = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        default=ExperimentLifeCycle.CREATED,
        choices=ExperimentLifeCycle.CHOICES)

    class Meta:
        ordering = ['created_at']


class ExperimentMetric(models.Model):
    """A model that represents an experiment metric at certain time."""
    experiment = models.ForeignKey(Experiment, related_name='metrics')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    values = JSONField()

    class Meta:
        ordering = ['created_at']


class ExperimentJob(DiffModel):
    """A model that represents job related to an experiment"""
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        null=False)
    experiment = models.ForeignKey(Experiment, related_name='jobs')
    definition = JSONField(help_text='The specific values for this job.')

    @property
    def last_status(self):
        return self.status.last()

    @property
    def started_at(self):
        status = self.status.filter(status=JobLifeCycle.BUILDING).first()
        if status:
            return status.created_at
        return None

    @property
    def finished_at(self):
        status = self.status.filter(status__in=JobLifeCycle.DONE_STATUS).last()
        if status:
            return status.created_at
        return None


post_save.connect(new_experiment_job, sender=ExperimentJob, dispatch_uid="experiment_job_saved")


class ExperimentJobStatus(models.Model):
    """A model that represents job status at certain time."""
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        null=False)
    job = models.ForeignKey(ExperimentJob, related_name='status')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    status = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        default=JobLifeCycle.CREATED,
        choices=JobLifeCycle.CHOICES)

    message = models.CharField(max_length=256, null=True, blank=True)
    details = JSONField(null=True, blank=True, default={})


post_save.connect(new_experiment_job_status,
                  sender=ExperimentJobStatus,
                  dispatch_uid="experiment_job_status_saved")
