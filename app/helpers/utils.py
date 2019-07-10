import math
import collections
import netaddr
import numpy as np
import base64
import re
from statistics import mean, median
import validators

import helpers.singletons


from typing import Dict, List, MutableMapping, Any, Optional, Union, Iterable, TYPE_CHECKING

if TYPE_CHECKING:
    from helpers.settings import Settings


def flatten_dict(d: MutableMapping, parent_key: str='', sep: str='.') -> Dict:
    items: List = []
    for k, v in d.items():
        new_key: str = parent_key + sep + k if parent_key else k
        if isinstance(v, collections.MutableMapping):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def dict_contains_dotkey(dict_value: Dict, key_name: str, case_sensitive: bool=True) -> bool:
    try:
        get_dotkey_value(dict_value, key_name, case_sensitive)
        return True
    except KeyError:
        return False


def get_dotkey_value(dict_value: Dict, key_name: str, case_sensitive: bool=True) -> Dict:
    """
    Get value by dot key in dictionary
    By default, the dotkey is matched case sensitive; for example, key "OsqueryFilter.process_name" will only match if
    the event contains a nested dictionary with keys "OsqueryFilter" and "process_name".
    By changing the case_sensitive parameter to "False", all elements of the dot key will be matched case insensitive.
    For example, key "OsqueryFilter.process_name" will also match a nested dictionary with keys "osqueryfilter" and
    "prOcEss_nAme".
    """
    keys: List[str] = key_name.split(".")

    for k in keys:
        if not case_sensitive:
            dict_keys: List = list(dict_value.keys())
            lowercase_keys: List = list(map(str.lower, dict_keys))
            lowercase_key_to_match: str = k.lower()
            if lowercase_key_to_match in lowercase_keys:
                matched_index: int = lowercase_keys.index(lowercase_key_to_match)
                dict_value = dict_value[dict_keys[matched_index]]
            else:
                raise KeyError
        else:
            dict_value = dict_value[k]

    return dict_value


def match_ip_ranges(source_ip: str, ip_cidr: List[str]) -> bool:
    return False if len(netaddr.all_matching_cidrs(source_ip, ip_cidr)) <= 0 else True


def shannon_entropy(data: Optional[str]) -> float:
    if not data:
        return 0
    entropy: float = 0
    for x in range(256):
        p_x: float = float(data.count(chr(x))) / len(data)
        if p_x > 0:
            entropy += - p_x * math.log(p_x, 2)
    return entropy


def extract_outlier_asset_information(fields: Dict, settings: 'Settings') -> List[str]:
    """
    :param fields: the dictionary containing all the event information
    :param settings: the settings object which also includes the configuration file that is used
    :return:
    """
    outlier_assets: List[str] = list()
    for (asset_field_name, asset_field_type) in settings.config.items("assets"):
        if dict_contains_dotkey(fields, asset_field_name, case_sensitive=False):

            asset_field_values_including_empty: List[List] = flatten_fields_into_sentences(fields,
                                                                               sentence_format=[asset_field_name])
            # also remove all empty asset strings
            asset_field_values: List = [sentence[0] for sentence in asset_field_values_including_empty \
                                        if "" not in sentence]

            for asset_field_value in asset_field_values:  # make sure we don't process empty process information,
                # for example an empty user field
                outlier_assets.append(asset_field_type + ": " + asset_field_value)

    return outlier_assets


# Convert a sentence value into a flat string, if possible
# If not, just return None
def flatten_sentence(sentence: Any=None) -> Optional[str]:
    if sentence is None:
        return None
    field_value: str

    if type(sentence) is list:
        # Make sure the list does not contain nested lists, but only strings.
        # If it's a nested list, we give up and return None
        if any(isinstance(i, list) or isinstance(i, dict) for i in sentence):
            return None
        else:
            # We convert a list value such as [1,2,3] into a single string, so the model can use it: 1-2-3
            field_value = " - ".join(str(x) for x in sentence)
            return field_value
    elif type(sentence) is dict:
        return None
    else:
        # We just cast to string in all other cases
        field_value = str(sentence)
        return field_value


# Convert a sentence format and a fields dictionary into a list of sentences.
# Example:
# sentence_format: hostname, username
# fields: {hostname: [WIN-DRA, WIN-EVB], draman}
# output: [[WIN-DRA, draman], [WIN-EVB, draman]]
def flatten_fields_into_sentences(fields: Dict, sentence_format: List) -> List[List]:
    sentences: List[List] = [[]]

    for i, field_name in enumerate(sentence_format):
        new_sentences: List[List] = []
        if type(get_dotkey_value(fields, field_name, case_sensitive=False)) is list:
            for field_value in get_dotkey_value(fields, field_name, case_sensitive=False):
                for sentence in sentences:
                    sentence_copy: List = sentence.copy()
                    sentence_copy.append(flatten_sentence(field_value))
                    new_sentences.append(sentence_copy)
        else:
            for sentence in sentences:
                sentence.append(flatten_sentence(get_dotkey_value(fields, field_name, case_sensitive=False)))
                new_sentences.append(sentence)

        sentences = new_sentences.copy()

    # Remove all sentences that contain fields that could not be parsed, and that have been flattened to "None".
    # We can't reasonably work with these, so we just ignore them.
    sentences = [sentence for sentence in sentences if None not in sentence]

    return sentences


def replace_placeholder_fields_with_values(placeholder: str, fields: Dict) -> str:
    # Replace fields from fieldmappings in summary
    regex = re.compile(r'\{([^\}]*)\}')
    field_name_list = regex.findall(placeholder)  # ['source_ip','destination_ip'] for example

    for field_name in field_name_list:
        if dict_contains_dotkey(fields, field_name, case_sensitive=False):
            field_value: str

            if type(get_dotkey_value(fields, field_name, case_sensitive=False)) is list:
                try:
                    field_value = ", ".join(get_dotkey_value(fields, field_name, case_sensitive=False))
                except TypeError:
                    field_value = "complex field " + field_name
            else:
                field_value = str(get_dotkey_value(fields, field_name, case_sensitive=False))

            placeholder = placeholder.replace('{' + field_name + '}', field_value)
        else:
            placeholder = placeholder.replace('{' + field_name + '}', "{field " + field_name + " not found in event}")

    return placeholder


def is_base64_encoded(_str: str) -> Union[None, bool, str]:
    try:
        decoded_bytes: bytes = base64.b64decode(_str)
        if base64.b64encode(decoded_bytes) == _str.encode("ascii"):
            return decoded_bytes.decode("ascii")
        return None # TODO maybe return False also ?
    except Exception:
        return False


def is_hex_encoded(_str: str) -> Union[bool, str]:
    try:
        decoded: int = int(_str, 16)
        return str(decoded)
    except Exception:
        return False


def is_url(_str: str) -> Union[bool, validators.utils.ValidationFailure]:
    try:
        return validators.url(_str)
    except Exception:
        return False


def get_decision_frontier(trigger_method: str, values_array: List, trigger_sensitivity: int,
                          trigger_on: Optional[str]=None) -> Union[int, float, np.float64]:
    
    decision_frontier: Union[int, float, np.float64]
    if trigger_method == "percentile":
        decision_frontier = get_percentile_decision_frontier(values_array, trigger_sensitivity)

    elif trigger_method == "pct_of_max_value":
        max_value: Union[int, float] = max(values_array)
        decision_frontier = np.float64(max_value * (trigger_sensitivity / 100))

    elif trigger_method == "pct_of_median_value":
        median_value: Union[int, float] = median(values_array)
        decision_frontier = np.float64(median_value * (trigger_sensitivity / 100))

    elif trigger_method == "pct_of_avg_value":
        avg_value: Union[int, float] = mean(values_array)
        decision_frontier = np.float64(avg_value * (trigger_sensitivity / 100))

    elif trigger_method == "mad" or trigger_method == "madpos":
        decision_frontier = get_mad_decision_frontier(values_array, trigger_sensitivity, trigger_on)

        # special case - if MAD is zero, then we use stdev instead of MAD, since more than half of all values are equal
        if decision_frontier == np.nanmedian(values_array):
            decision_frontier = get_stdev_decision_frontier(values_array, 1, trigger_on)

        # special case - if MADPOS is being used, we never want to return a negative MAD, so cap it at 0
        if trigger_method == "madpos":
            decision_frontier = np.float64(max([decision_frontier, 0]))

    elif trigger_method == "stdev":
        decision_frontier = get_stdev_decision_frontier(values_array, trigger_sensitivity, trigger_on)
    elif trigger_method == "float":
        decision_frontier = np.float64(trigger_sensitivity)
    else:
        raise ValueError("Unexpected trigger method " + trigger_method + ", could not calculate decision frontier")

    if decision_frontier < 0:
        # Could not do "from helpers.singletons import logging" due to circle import
        helpers.singletons.logging.logger.warning("negative decision frontier %.2f, this will not generate any "
                                                  "outliers", decision_frontier)

    return decision_frontier


# Calculate percentile decision frontier
# Example: values array is [0 5 10 20 30 2 5 5]
# trigger_sensitivity is 10 (meaning: 10th percentile)
def get_percentile_decision_frontier(values_array: List, percentile: int) -> Union[int, float, np.float64]:
    res: Union[int, float, np.float64] = np.percentile(list(set(values_array)), percentile)
    return res


def get_stdev_decision_frontier(values_array: List, trigger_sensitivity: int,
                                trigger_on: Optional[str]) -> Union[None, int, float, np.float64]:
    stdev: Union[int, float, np.float64] = np.std(values_array)

    decision_frontier: Union[None, int, float, np.float64]
    if trigger_on == "high":
        decision_frontier = np.nanmean(values_array) + trigger_sensitivity * stdev

    elif trigger_on == "low":
        decision_frontier = np.nanmean(values_array) - trigger_sensitivity * stdev
    else:
        raise ValueError("Unexpected trigger condition " + str(trigger_on) + ", could not calculate decision frontier")

    return decision_frontier


def get_mad_decision_frontier(values_array: List, trigger_sensitivity: int,
                              trigger_on: Optional[str]) -> Union[int, float, np.float64]:
    # median absolute deviation
    mad: Union[int, float, np.float64] = np.nanmedian(np.absolute(values_array - np.nanmedian(values_array, 0)), 0)

    decision_frontier: Union[None, int, float, np.float64]
    if trigger_on == "high":
        decision_frontier = np.nanmedian(values_array) + trigger_sensitivity * mad

    elif trigger_on == "low":
        decision_frontier = np.nanmedian(values_array) - trigger_sensitivity * mad
    else:
        raise ValueError("Unexpected trigger condition " + str(trigger_on) + ", could not calculate decision frontier")

    return decision_frontier


def is_outlier(term_value_count: int, decision_frontier: Union[int, float, np.float64],
               trigger_on: Optional[str]) -> Union[int, float, np.float64, bool]:
    if trigger_on == "high":
        if term_value_count > decision_frontier:
            return True
        else:
            return False
    elif trigger_on == "low":
        if term_value_count < decision_frontier:
            return decision_frontier
        else:
            return False
    else:
        raise ValueError("Unexpected outlier trigger condition " + str(trigger_on))


def nested_dict_values(d: Dict) -> Iterable[Any]:
    for v in d.values():
        if isinstance(v, dict):
            yield from nested_dict_values(v)
        else:
            yield v
