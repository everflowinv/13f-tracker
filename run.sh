{\rtf1\ansi\ansicpg936\cocoartf2868
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\paperw11900\paperh16840\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural\partightenfactor0

\f0\fs24 \cf0 #!/bin/bash\
\
# \uc0\u21160 \u24577 \u33719 \u21462 \u24403 \u21069 \u33050 \u26412 \u25152 \u22312 \u30340 \u32477 \u23545 \u36335 \u24452 \u65292 \u30830 \u20445 \u20174 \u20219 \u20309 \u30446 \u24405 \u25191 \u34892 \u37117 \u19981 \u20250 \u25253 \u38169 \
DIR="$( cd "$( dirname "$\{BASH_SOURCE[0]\}" )" >/dev/null 2>&1 && pwd )"\
\
# \uc0\u26234 \u33021 \u26816 \u27979 \u65306 \u22914 \u26524 \u23384 \u22312 \u34394 \u25311 \u29615 \u22659 \u65292 \u20248 \u20808 \u20351 \u29992 \u34394 \u25311 \u29615 \u22659 \u20013 \u30340  Python\
if [ -f "$DIR/venv/bin/python" ]; then\
    PYTHON_EXEC="$DIR/venv/bin/python"\
else\
    # \uc0\u21542 \u21017 \u22238 \u36864 \u65288 Fallback\u65289 \u21040 \u31995 \u32479 \u40664 \u35748 \u30340  python3\
    PYTHON_EXEC="python3"\
fi\
\
# \uc0\u25191 \u34892 \u24213 \u23618 \u30340  Python \u33050 \u26412 \u65292 \u24182 \u23558 \u22823 \u27169 \u22411 \u20256 \u36807 \u26469 \u30340 \u25152 \u26377 \u21442 \u25968 \u65288 \u22914  --institution 0001762304 compare\u65289 \u21407 \u26679 \u20256 \u36882 \
"$PYTHON_EXEC" "$DIR/scripts/13f_skill.py" "$@"}