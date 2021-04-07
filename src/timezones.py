# Keypirinha launcher (keypirinha.com)

import keypirinha as kp
import keypirinha_util as kpu
import keypirinha_net as kpnet
import os
import sys
import locale
import re
import json
from time import gmtime, strftime

class timezones(kp.Plugin):
    ITEMCAT_RESULT = kp.ItemCategory.USER_BASE + 1
    ITEMCAT_RELOAD_DEFS = kp.ItemCategory.USER_BASE + 2

    MILITARY_TIME_DEFAULT = True
    MILITARY_TIME_PICKED = MILITARY_TIME_DEFAULT

    SEPARATORS_DEFAULT = "to in"
    SEPARATORS_PICKED = SEPARATORS_DEFAULT

    TIME_ZONE_DEFAULT = "UTC"
    TIME_ZONE_PICKED = TIME_ZONE_DEFAULT

    TIMEZONEDEF_FILE = "timezonedefs.json"
    def __init__(self):
        super().__init__()

    def read_defs(self, defs_file):
        defs = None
        try:
            # Either file exist in the user profile dir
            timedefs = os.path.join(kp.user_config_dir(),"data",defs_file)
            if os.path.exists(timedefs):
                self.info(f"Loading custom conversion definition file '{timedefs}'")
                self.customized_config = True
                with open(timedefs, "r", encoding="utf-8") as f:
                    defs = json.load(f)
            else: # ... or it may be in the plugin
                try:
                    defs_text = self.load_text_resource(defs_file)
                    defs = json.loads(defs_text)
                    self.dbg(f"Loaded internal conversion definitions '{defs_file}'")
                except Exception as exc:
                    defs = { "timezones" : [] }
                    self.dbg(f"Did not load internal definitions file '{defs_file}', {exc}")
                    pass
        except Exception as exc:
            self.warn(f"Failed to load definitions file '{timedefs}', {exc}")

        return defs

    def on_start(self):
        self.logo = 'res://%s/%s'%(self.package_full_name(),'globe-with-meridians.png')
        defs = self.read_defs(self.TIMEZONEDEF_FILE)
        self.timezones = defs['timezones']
        self.set_actions(self.ITEMCAT_RESULT, [
            self.create_action(
                name="copy",
                label="Copy",
                short_desc="Copy the converted time")])

        self.set_actions(self.ITEMCAT_RELOAD_DEFS, [
            self.create_action(
                name="reload",
                label="Reload",
                short_desc="Reload the custom timezone definition file")])
        pass

    def on_catalog(self):
        self._load_settings()
        catalog = []

        output_timezones = self.TIME_ZONE_PICKED
        for output in output_timezones:
            matching_timezone = self._find_timezone(output)
            for t in self.timezones:
                diff = t['difference_hours'] - matching_timezone['difference_hours']
                if (diff > 0):
                    diff = f"+{diff}"
                catalog.append(self.create_item(
                    category=kp.ItemCategory.KEYWORD,
                    label=f"Timezone: {t['timezone']}",
                    short_desc=f"{t['desc']} ({diff} {matching_timezone['timezone']})",
                    target=t['timezone'],
                    icon_handle=self.load_icon(self.logo),
                    args_hint=kp.ItemArgsHint.FORBIDDEN,
                    hit_hint=kp.ItemHitHint.NOARGS))

        self.set_catalog(catalog)
        pass

    def on_suggest(self, user_input, items_chain):
        reg = self.get_regex(self.timezones)
        parsed_input = reg.match(user_input.upper())
        if parsed_input is None and len(items_chain) < 1:
            return

        if ('now' in user_input):
            user_input = re.sub(self._now_regex(), strftime("%H:%M UTC", gmtime()), user_input)
        suggestions = []
        timezones_reg = self._timezones_regex(self.timezones)
        separators_reg = self._separators_regex()
        joined_reg = separators_reg + '{1}' + timezones_reg + '+\s*$' # {1} to ensure there is only one separator
        if (re.search(joined_reg, user_input.upper())): #user specified output
            r1 = re.findall(joined_reg, user_input.upper())
            timezone_picked = r1[-1][-1]
            source = self._source_data(user_input.upper(), timezone_picked)
            destination = self._destination_data(source, timezone_picked)
            if(self.MILITARY_TIME_PICKED):
                suggestions.append(self._destination_24h(source, destination))
            else:
                suggestions.append(self._destination_ampm(source, destination))
        else: #default output
            for timezone_picked in self.TIME_ZONE_PICKED:
                source = self._source_data(user_input.upper(), timezone_picked)
                destination = self._destination_data(source, timezone_picked)
                if(self.MILITARY_TIME_PICKED):
                    suggestions.append(self._destination_24h(source, destination))
                else:
                    suggestions.append(self._destination_ampm(source, destination))

        self.set_suggestions(suggestions, kp.Match.ANY, kp.Sort.NONE)
        pass

    def on_execute(self, item, action):
        pass

    def _destination_24h(self, source, destination):
        conversions = self._calculations(source, destination)
        output_result = f'{conversions["hours"]}:{conversions["minutes"]} {conversions["timezone"]}'
        return self.create_item(
            category=self.ITEMCAT_RESULT,
            label=output_result,
            short_desc=f'{conversions["hours"]}:{conversions["minutes"]} {conversions["timezone"]} ({conversions["difference_short"]}) {conversions["additional"]}',
            target=output_result,
            icon_handle=self.load_icon(self.logo),
            args_hint=kp.ItemArgsHint.FORBIDDEN,
            hit_hint=kp.ItemHitHint.IGNORE)

    def _destination_ampm(self, source, destination):
        conversions = self._calculations(source, destination)
        
        meridiem = 'AM'
        hours = conversions["hours"]
        if (int(hours) > 12):
            meridiem = 'PM'
            hours = str(abs(12 -int(hours)))
        elif (int(hours) == 12):
            meridiem = 'PM'
        elif (int(hours) == 0):
            hours = '12'

        output_result = f'{hours}:{conversions["minutes"]}{meridiem} {conversions["timezone"]}'
        return self.create_item(
            category=self.ITEMCAT_RESULT,
            label=output_result,
            short_desc=f'{hours}:{conversions["minutes"]}{meridiem} {conversions["timezone"]} ({conversions["difference_short"]}) {conversions["additional"]}',
            target=output_result,
            args_hint=kp.ItemArgsHint.FORBIDDEN,
            hit_hint=kp.ItemHitHint.IGNORE)

    def _calculations(self, source, destination):
        new_hours = int(source['hour'])
        if (not bool(source['military'])):
            if (source['meridiem'].upper() == "AM" and new_hours == 12):
                new_hours = 0
            elif (source['meridiem'].upper() == "PM" and new_hours < 12):
                new_hours = new_hours + 12

        additional = ''
        new_hours = new_hours + destination['difference_hours']
        new_minutes = int(source['min'])
        new_minutes = new_minutes + destination['difference_minutes']
        if (new_minutes > 59):
            new_minutes = 60 - new_minutes
            new_hours = new_hours + 1
        elif (new_minutes < 0):
            new_minutes = 60 + new_minutes
            new_hours = new_hours - 1
        
        if (new_hours > 23):
            days = 0
            while(new_hours > 23):
                days = days + 1
                new_hours = abs(24 - new_hours)
            additional = f'(+{days} days)'
        elif (new_hours < 0):
            days = 0
            while(new_hours < 0):
                days = days + 1
                new_hours = 24 + new_hours
            additional = f'(-{days} days)'

        dif = destination["difference_hours"]
        dif_minutes = ''
        if (destination['difference_minutes'] != 0):
            dif_minutes = f":{destination['difference_minutes']}"
            if (int(dif) < 0 or int(destination['difference_minutes']) < 0):
                dif_minutes = f":{str(destination['difference_minutes']* -1).zfill(2)}" 

        dif = f'+{dif}' if (dif >= 0) else f'{dif}'
        dif = f'{dif}{dif_minutes}'

        response = dict()
        response['hours'] = str(new_hours)
        response['minutes'] = str(new_minutes).zfill(2)
        response['timezone'] = destination["timezone"]
        response['difference_short'] = dif
        response['additional'] = additional
        return response

    def _find_timezone(self, timezone_to_find):
        filter_results = list(filter(lambda x: x['timezone'] == timezone_to_find, self.timezones))
        if (len(filter_results) == 0):
            relevant_timezones = list(filter(lambda x: 'aliases' in x and len(x['aliases']) > 0, self.timezones))
            filter_results = list(filter(lambda x: timezone_to_find in x['aliases'], relevant_timezones))
        if (len(filter_results) > 0):
            return filter_results[-1]
        return {}

    def _destination_data(self, source, timezone_picked):
        input_timezone = self._find_timezone(source['timezone'])
        output_timezone = self._find_timezone(timezone_picked)
        
        difference_hours = output_timezone['difference_hours'] - input_timezone['difference_hours']
        difference_minutes = output_timezone['difference_minutes'] - input_timezone['difference_minutes']
        
        response = dict()
        response['timezone'] = output_timezone['timezone']
        response['difference_hours'] = difference_hours
        response['difference_minutes'] = difference_minutes
        return response

    def _source_data(self, user_input, timezone_picked):
        user_input = user_input.upper()
        response = dict()
        response['min'] = '00'
        response['hour'] = '0'
        response['meridiem'] = ''
        response['timezone'] = timezone_picked
        response['military'] = True

        h12 = self._12H_regex()
        minutes = self._minutes_regex()
        ampm = self._am_pm_regex()
        h12_regex = f'{h12}{minutes}?{ampm}'

        if (re.search(minutes, user_input)):
            r1 = re.findall(minutes, user_input)
            response['min'] = r1[-1][-1]

        if (re.search(ampm, user_input)):
            r1 = re.findall(ampm, user_input)
            response['meridiem'] = r1[-1]
            response['military'] = False

        if (re.search(self._24H_regex(), user_input) and not re.search(self._am_pm_regex(), user_input)):
            r1 = re.findall(self._24H_regex(), user_input)
            response['hour'] = r1[0]
            response['military'] = True
        elif (re.search(h12_regex, user_input)):
            r1 = re.findall(h12_regex, user_input)
            response['hour'] = r1[0][0]
            response['military'] = False

        if (re.search(self._timezones_regex(self.timezones), user_input)):
            r1 = re.findall(self._timezones_regex(self.timezones), user_input)
            filtered = list(filter(None,r1))
            response['timezone'] = filtered[0]
        return response

    def get_regex(self, time_zones_array):
        h24 = self._24H_regex()
        h12 = self._12H_regex()
        now = self._now_regex()
        minutes = self._minutes_regex()
        ampm = self._am_pm_regex()
        timezones = self._timezones_regex(time_zones_array)
        separators = self._separators_regex()
        INPUT_PARSER = f'^(({now})|({h24}{minutes}?)|({h12}{minutes}?{ampm}))?{timezones}?\s*({separators}{timezones})?$'
        return re.compile(INPUT_PARSER)

    def _minutes_regex(self):
        return r'(:([0-5][0-9]))'

    def _24H_regex(self):
        return r'([0-1]?[0-9]|2[0-3])'

    def _12H_regex(self):
        return r'(1[0-2]|0?[1-9])'

    def _now_regex(self):
        return r'([Nn][Oo][Ww])'

    def _am_pm_regex(self):
        return r'\s*([AaPp][Mm])'

    def _timezones_regex(self, time_zones_array):
        flattened = []
        for i in time_zones_array:
            flattened.append(i['timezone'])
            if ('aliases' in i and len(i['aliases']) > 0):
                for j in i['aliases']:
                    flattened.append(j.upper())
                
        pipes = '|'.join(flattened)
        return f'\s*({pipes})'

    def _separators_regex(self):
        separators = []
        for s in self.SEPARATORS_PICKED:
            separators.append(s.upper())
        return f'\s*({"|".join(separators)})'

    def _load_settings(self):
        settings = self.load_settings()
        section_counter = 0
        for config_section in settings.sections():
            if config_section.startswith("#") or not config_section.upper().startswith("TIMEZONE/"):
                continue
            section_counter = section_counter + 1
            new_timezone = config_section[len("timezone/"):]
            match = self._find_timezone(new_timezone)
            if (match == {}): # New timezone
                new_obj = dict()
                new_obj['timezone'] = new_timezone
                new_obj['desc'] = settings.get_stripped("desc", section=config_section, fallback=f"Timezone for {new_timezone}")
                new_obj['difference_hours'] = int(settings.get_stripped("difference_hours", section=config_section, fallback=0))
                new_obj['difference_minutes'] = int(settings.get_stripped("difference_minutes", section=config_section, fallback=0))
                aliases = settings.get_stripped("aliases", section=config_section, fallback=None)
                if aliases:
                    new_obj['aliases'] = []
                    for a in settings.get_stripped('aliases', section=config_section, fallback=None).split(","):
                        new_obj['aliases'].append(a.upper())
                self.timezones.append(new_obj)
            else: # Existing timezone
                index = self.timezones.index(match)
                aliases = settings.get_stripped("aliases", section=config_section, fallback=None).split(",")
                if aliases:
                    for s in settings.get_stripped("aliases", section=config_section, fallback=None).split(","):
                        if (s not in self.timezones[index]['aliases']):
                            self.timezones[index]['aliases'].append(s.upper())

        self.MILITARY_TIME_PICKED = settings.get_bool(
            "use_military_time", "main", 
            self.MILITARY_TIME_DEFAULT
        )

        self.TIME_ZONE_PICKED = settings.get_stripped(
            "output_timezones", "main",
            fallback=self.TIME_ZONE_DEFAULT).split()

        self.SEPARATORS_PICKED = settings.get_stripped(
            "separators", "main",
            fallback=self.SEPARATORS_DEFAULT).split()

        self.info(f"Loaded {str(section_counter)} custom timezones")
        pass