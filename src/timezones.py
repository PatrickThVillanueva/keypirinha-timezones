# Keypirinha launcher (keypirinha.com)

import keypirinha as kp
import keypirinha_util as kpu
import keypirinha_net as kpnet
import os
import sys
import locale
import re
import json

class timezones(kp.Plugin):
    ITEMCAT_RESULT = kp.ItemCategory.USER_BASE + 1
    ITEMCAT_RELOAD_DEFS = kp.ItemCategory.USER_BASE + 2

    ITEM_LABEL_PREFIX = "Time: "
    
    TIME_FORMAT_DEFAULT = "24H"
    TIME_FORMAT_PICKED = TIME_FORMAT_DEFAULT

    TIME_ZONE_DEFAULT = "UTC"
    TIME_ZONE_PICKED = TIME_ZONE_DEFAULT

    TIME_FORMATS = ["24H", "AMPM"]

    TIMEZONEDEF_FILE = "timezonedefs.json"

    def __init__(self):
        super().__init__()

#ex: 1AM EST
#ex: 1:00 EST
#ex: 9PM EST
#ex: 10:24
#ex: 13:37 CET
#ex: 12:31PM CEST
#ex: 23:59 PDT -> Next day for UTC!
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

    def add_defs(self, defs):
        if "timezones" in defs:
            def_timezones = defs["timezones"]
            for item in def_timezones.items():
                new_timezone_name = item["timezone"]
                new_timezone_desc = item["desc"]
                new_timezone_hours = item["difference_hours"]
                new_timezone_minutes = item["difference_minutes"]
                if not new_measure_name in self.timezones:
                    self.timezones[new_measure_name] = item
                for alias in item["aliases"]:
                    alias = alias.lower()
                    if alias in self.all_units:
                        continue
                    else:
                        timezone = item["aliases"]
                        if not alias in timezone["aliases"]:
                            timezone["aliases"] = timezone["aliases"] + [alias]
                    self.all_units[alias] = measure
                    self.measure_aliases[new_measure_name][alias] = measure

    def on_start(self):
        defs = self.read_defs(self.TIMEZONEDEF_FILE)
        self.timezones = defs['timezones']
        self.add_defs(self.TIMEZONEDEF_FILE)

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
        reg = self.get_regex(self.timezones)

        catalog = []
        catalog.append(self.create_item(
            category=kp.ItemCategory.KEYWORD,
            label="Timezone ",
            short_desc="Convert timesonze",
            target="timezone",
            args_hint=kp.ItemArgsHint.REQUIRED,
            hit_hint=kp.ItemHitHint.NOARGS))

        self.set_catalog(catalog)
        pass

    def on_suggest(self, user_input, items_chain):
        reg = self.get_regex(self.timezones)
        parsed_input = reg.match(user_input)
        if parsed_input is None and len(items_chain) < 1:
            return

        source = self._source_data(user_input)
        destination = self._destination_data(source)
        if(self.TIME_FORMAT_PICKED == "ampm"):
            self.set_suggestions(self._destination_ampm(source, destination), kp.Match.ANY, kp.Sort.NONE)
        else:
            self.set_suggestions(self._destination_24h(source, destination), kp.Match.ANY, kp.Sort.NONE)
        pass

    def on_execute(self, item, action):
        pass

    def _destination_24h(self, source, destination):
        additional = ''
        hours = int(destination["hour"])
        if (destination['hour'] > 23):
            additional = '(Next day)'
            hours = abs(24 - hours)
        elif (destination['hour'] < 0):
            additional = '(Previous day)'
            hours = hours + 24

        output_hours = str(hours).zfill(2)
        output_min = str(destination["min"]).zfill(2)
        output_result = f'{output_hours}:{output_min} {destination["timezone"]}'
        dif = destination["difference"]
        if (dif >= 0):
            dif = f'+{dif}'
            
        suggestions = []
        suggestions.append(self.create_item(
            category=self.ITEMCAT_RESULT,
            label=output_result,
            short_desc=f'{output_hours}:{output_min} {destination["timezone"]} ({dif}) {additional}',
            target=output_result,
            args_hint=kp.ItemArgsHint.FORBIDDEN,
            hit_hint=kp.ItemHitHint.IGNORE))

        return suggestions

    #12AM = 0:00
    def _destination_ampm(self, source, destination):
        output_result = ''
        output_meridiem = source['meridiem']
        output_hours = source['hour']
        
        if (int(output_hours) > 12):
            if (source['meridiem'] == "am"):
                output_meridiem = "pm"
                output_result = f'{output_hours}:{source["min"]}{output_meridiem} {output_timezone["timezone"]}'
            else:
                output_meridiem = "am"
                output_result = f'{output_hours}:{source["min"]}{output_meridiem} {output_timezone["timezone"]} (Next day)'
            output_hours = str(int(output_hours) - 12).zfill(2)

        suggestions = []
        suggestions.append(self.create_item(
            category=self.ITEMCAT_RESULT,
            label=f'{output_hours}:{output_minutes}{output_meridiem}',
            short_desc=output_timezone["timezone"],
            target=output_result,
            args_hint=kp.ItemArgsHint.FORBIDDEN,
            hit_hint=kp.ItemHitHint.IGNORE))

        return suggestions

    def _find_timezone(self, timezone_to_find):
        filter_results = filter(lambda x: x['timezone'] == timezone_to_find, self.timezones)
        return list(filter_results)[-1]

    def _destination_data(self, source):
        input_timezone = self._find_timezone(source['timezone'])
        output_timezone = self._find_timezone(self.TIME_ZONE_PICKED)

        difference_hours = input_timezone['difference_hours'] - output_timezone['difference_hours']
        difference_minutes = input_timezone['difference_minutes'] - output_timezone['difference_minutes']
        hours = int(source['hour']) + difference_hours
        minutes = int(source['min']) + difference_minutes
        
        response = dict()
        response['min'] = minutes
        response['hour'] = hours
        response['timezone'] = output_timezone['timezone']
        response['difference'] = difference_hours
        return response

    def _source_data(self, user_input):
        response = dict()
        response['min'] = '00'
        response['hour'] = '0'
        response['meridiem'] = ''
        response['timezone'] = self.TIME_ZONE_PICKED
        response['timeformat'] = self.TIME_FORMAT_PICKED

        h12 = self._12H_regex()
        minutes = self._minutes_regex()
        ampm = self._am_pm_regex()
        h12_regex = f'{h12}{minutes}?{ampm}'

        if (re.search(self._minutes_regex(), user_input)):
            r1 = re.findall(self._minutes_regex(), user_input)
            response['min'] = r1[-1][-1]

        if (re.search(self._am_pm_regex(), user_input)):
            r1 = re.findall(self._am_pm_regex(), user_input)
            response['meridiem'] = r1[-1]
            response['timeformat'] = 'ampm'

        if (re.search(self._24H_regex(), user_input) and not re.search(self._am_pm_regex(), user_input)):
            r1 = re.findall(self._24H_regex(), user_input)
            response['hour'] = r1[0]
            response['timeformat'] = '24H'
        elif (re.search(h12_regex, user_input)):
            r1 = re.findall(h12_regex, user_input)
            response['hour'] = r1[0][0]
            response['timeformat'] = 'ampm'

        if (re.search(self._timezones_regex(self.timezones), user_input)):
            r1 = re.findall(self._timezones_regex(self.timezones), user_input)
            filtered = list(filter(None,r1))
            response['timezone'] = filtered[0]
        return response

    def get_regex(self, time_zones_array):
        h24 = self._24H_regex()
        h12 = self._12H_regex()
        minutes = self._minutes_regex()
        ampm = self._am_pm_regex()
        timezones = self._timezones_regex(time_zones_array)
        INPUT_PARSER = f'^(({h24}{minutes}?)|({h12}{minutes}?{ampm}))+\s*{timezones}?$'

        return re.compile(INPUT_PARSER)

    def _minutes_regex(self):
        return r'(:([0-5][0-9]))'

    def _24H_regex(self):
        return r'([01][0-9]|2[0-3])' 

    def _12H_regex(self):
        return r'(1[0-2]|0?[1-9])'

    def _am_pm_regex(self):
        return r'\s*([AaPp][Mm])'

    def _timezones_regex(self, time_zones_array):
        attrs = [o['timezone'] for o in time_zones_array]
        pipes = '|'.join(attrs)
        return '\s*(' + pipes + ')'

    def _load_settings(self):
        settings = self.load_settings()

        sections = self.load_settings().sections()
        for config_section in sections:
            if config_section.startswith("#") or not config_section.lower().startswith("timezone/"):
                continue
            new_timezone = config_section[len("r/"):]

        self.TIME_FORMAT_PICKED = settings.get_enum(
            "time_format", 
            "main", 
            fallback=self.TIME_FORMAT_DEFAULT, 
            enum=self.TIME_FORMATS
        ).lower()

        self.TIME_ZONE_PICKED = settings.get_stripped(
            "output_timezone",
            fallback=self.TIME_ZONE_DEFAULT)
        pass