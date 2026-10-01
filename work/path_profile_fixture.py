"""Strip only PATH diagnostic annotations for older scoped extraction fixtures.

The PATH fixture independently compiles all new bodies and checks the complete
reverse-strip oracle. This helper does not remove gameplay bodies or arithmetic.
"""
import re
def strip(text):
 text=re.sub(r'^    // BEGIN PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY\n.*?^    // END PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY\n','',text,flags=re.M|re.S)
 text=''.join(line for line in text.splitlines(True) if 'PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY' not in line)
 text=text.replace(' || !strcmp(category,"PATH_SAMPLE")','')
 return text.replace('\tif (kToNodeCacheData.iGenerationID==finder->GetCurrentGenerationID())\n\t{\n\t\treturn;\n\t}', '\tif (kToNodeCacheData.iGenerationID==finder->GetCurrentGenerationID())\n\t\treturn;')
