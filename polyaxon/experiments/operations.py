import logging

from experiments.tasks import build_experiment
from experiments.utils import get_valid_experiment
from pipelines.celery_task import ClassBasedTask, OperationRunError
from polyaxon.celery_api import app as celery_app
from polyaxon.config_settings import CeleryOperationTasks

logger = logging.getLogger('polyaxon.tasks.experiments')


class ScheduleExperimentTask(ClassBasedTask):
    @staticmethod
    def _run(task_bind, *args, **kwargs):
        experiment_id = kwargs['experiment_id']
        experiment = get_valid_experiment(experiment_id=experiment_id)
        if not experiment:
            raise OperationRunError(
                'The Experiment `{}` does not exist anymore.'.format(experiment_id))
        build_experiment.apply_async(experiment_id=experiment_id)


@celery_app.task(name=CeleryOperationTasks.EXPERIMENTS_SCHEDULE, bind=True)
def schedule_experiment(self, experiment_id):
    ScheduleExperimentTask.run(task_bind=self, experiment_id=experiment_id)
