import qase.api_client_v1

from qase_helper.lib.config import Config


class Converter(object):
    def __init__(self, config: Config):
        self.configuration = qase.api_client_v1.Configuration()
        self.configuration.api_key['TokenAuth'] = config.qase_token

    def convert_plan(self, project_code, name):
        with qase.api_client_v1.ApiClient(self.configuration) as api_client:
            api_instance = qase.api_client_v1.PlansApi(api_client)
            response = api_instance.get_plans(project_code)
            return self._get_by_name(response.result.entities, name)

    def convert_milestone(self, project_code, name):
        with qase.api_client_v1.ApiClient(self.configuration) as api_client:
            api_instance = qase.api_client_v1.MilestonesApi(api_client)
            response = api_instance.get_milestones(project_code)
            return self._get_by_name(response.result.entities, name)

    def convert_environment(self, project_code, name):
        with qase.api_client_v1.ApiClient(self.configuration) as api_client:
            api_instance = qase.api_client_v1.EnvironmentsApi(api_client)
            response = api_instance.get_environments(project_code)
            return self._get_by_name(response.result.entities, name)

    def _get_by_name(self, entities, name):
        for entity in entities:
            if entity.title == name:
                return entity.id
        return None
