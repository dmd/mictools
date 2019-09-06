#!/usr/bin/env python3

# this is a utility for Daniel to make it easier
# to move tapes into the mailslot for sending to Iron Mountain

from sh import mtx, bconsole, echo
import sys
import re

tape_device = '/dev/tape/by-serial/bs_sch-STK_SL150_464970G+1304SY0600-sch'

# you should have given 1, 2, 3, or 4 tapes as arguments

if len(sys.argv) < 2 or len(sys.argv) > 5:
    print('You must specify 1-4 tapes.')
    sys.exit(1)

tapes = sys.argv[1:]

# sanity check; all tapes should be 8 chars and end in M8

if len(tapes) != len([k for k in tapes if k.endswith('M8') and len(k) == 8]):
    print(f'Got arguments: {tapes}.')
    print('All tape IDs should be 8 characters long and end in M8.')
    sys.exit(1)

# no repeated tapes allowed

if len(tapes) != len(set(tapes)):
    print('You may not repeat the same tape ID more than once.')
    sys.exit(1)

# check if we have 4 empty mailslots
raw_slots = mtx('-f', tape_device, 'status')

empty_mailslots = [k for k in raw_slots.split('\n') if 'IMPORT/EXPORT:Empty' in k]

if len(empty_mailslots) != 4:
    print(f'Need 4 empty mailslots; found {len(empty_mailslots)}.')
    sys.exit(1)

mailslots = list(map(lambda sub:''.join([ele for ele in sub if ele.isnumeric()]), empty_mailslots))

# now we need to figure out which slots are which tapes

storage_slots = [k for k in raw_slots.split('\n')
             if '  Storage Element' in k
             and 'Full' in k]

if len(storage_slots) == 0:
    print('Failed to get slots.')
    sys.exit(1)

slotmap = {}
for slot in storage_slots:
    (_, _, _, slotnumber, _, _, _, tapeid) = re.split(':|=| +', slot)
    slotmap[tapeid] = slotnumber

for tape in tapes:
    if tape not in slotmap:
        print(f'Could not find tape {tape} in library.')
        sys.exit(1)

# ready to move tapes!

for mailboxnum, tapeid in enumerate(tapes):
    print(f'Move tape {tapeid} from slot {slotmap[tapeid]} to mailbox {mailboxnum} ({mailslots[mailboxnum]}).')
    print(mtx('-f', tape_device, 'transfer', slotmap[tapeid], mailslots[mailboxnum]))

# update slots

bconsole(echo('-e','update slots storage=sl150-robot\n\n'))
print('Updated bacula slots.')
