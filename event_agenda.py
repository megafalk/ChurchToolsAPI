import pandas as pd
from churchtools_api import churchtools_api as cta
import secure.config as config

if __name__ == '__main__':
    api = cta.ChurchToolsApi(domain=config.ct_domain, ct_token=config.ct_token)
    event_id = input('Please enter your event id: ')
    agenda = api.get_event_agenda(event_id)
    if agenda == None:
        print('This event has no agenda')
        exit()
    agenda_docx = api.get_event_agenda_docx(agenda=agenda,serviceGroups= {} )
    agenda_docx.save('agenda.docx')
    pass