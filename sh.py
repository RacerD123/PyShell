#/bin/env python3

import os, sys, signal, time

CMD_ENDERS = (" ", "\n", "\t", ";", "&", "|", ">", "<")
HOMEDIR = os.getenv('HOME')
outQueue = [] #A queue of stuff to be prepended to prompt
bgJobs = {} #A dictionary of pid:cmd key-value pairs
fgJobs = {} #A dictionary of pid:cmd key-value pairs

def newProcess(cmd, args,
               errorMsg="Unknown Command \"{0}\"", fileErrorMsg="Error Opening \"{0}\"",
               redir=None, outdir=None):
    tmp = " ".join(args).split('|')
    if len(tmp) > 1:
        #Piping
        cmd = tmp
        first = cmd[0].strip().split()
        second = cmd[1].strip().split()
        print(first, second)
        r, w = os.pipe() #Read, write ends of pipe
        firstPID = os.fork()
        if not firstPID:
            #First Child
            os.dup2(w, 1)
            os.close(w)
            try:
                os.execvp(first[0], first)
            except FileNotFoundError: #Incorrect Command catching
                print(fileErrorMsg.format(first))
                sys.exit()
        secondPID = os.fork()
        if not secondPID:
            #Second Child
            os.dup2(r, 0)
            os.close(r)
            try:
                os.execvp(second[0], second)
            except FileNotFoundError: #Incorrect Command catching
                print(fileErrorMsg.format(second))
                sys.exit()
        return {firstPID: first, secondPID: second}
    else:
        #Not Piping
        pid = os.fork()
        if not pid:
            try:
                if redir is not None: #<
                    try:
                        fin = os.open(redir, os.O_RDONLY)
                    except FileNotFoundError:
                        print (fileErrorMsg.format(redir))
                        sys.exit()
                    os.dup2(fin, 0)
                    os.close(fin)

                if outdir is not None: #>
                    try:
                        fout = os.open(outdir, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
                    except FileNotFoundError:
                        print (fileErrorMsg.format(outdir))
                        sys.exit()
                    os.dup2(fout, 1)
                    # os.write(fout, bytes("TEST", 'UTF-8'))
                    os.close(fout)

                os.execvp(cmd, args)
            except FileNotFoundError:
                print(errorMsg.format(cmd))
                sys.exit()
        return pid

def run(str):
    global outQueue, bgJobs, fgJobs
    orig = str
    if "&" in str:
        bg = True
    else:
        bg = False
    str = str.replace('&','')
    fin = str.split('<')
    fin = fin[1] if len(fin)>1 else None
    fout = None
    if fin is not None: # < first
        fout = fin.split('>')
        if len(fout) > 1: # < >, so I need to fix fin's file name
            fin = fout[0]
            fout = fout[1]
        else: #Checking > <
            fout = str.split('<')[0].split('>')
            if len(fout) > 1: # > <
                fout = fout[1]
            else: # No >
                fout = None
    else: # Checking >
        fout = str.split('>')
        fout = fout[1] if len(fout)>1 else None
    cmd = str.split('>')[0].split('<')[0].split()
    if fin is not None:
        fin = fin.strip()
    if fout is not None:
        fout = fout.strip()
    #print("\"{}\"".format(cmd))
    #print("\"{}\"".format(fin))
    #print("\"{}\"".format(fout))
    pid = newProcess(cmd[0], cmd, redir=fin, outdir=fout)
    if "|" in orig:
        fgJobs.update(pid)
    elif bg:
        bgJobs[pid] = orig
    else:
        fgJobs[pid] = orig

def prompt():
    global outQueue, bgJobs, fgJobs
    while fgJobs:
        time.sleep(1)
    for i in outQueue:
        print(i)
    outQueue = []
    promptLine = os.getcwd().replace(HOMEDIR, '~') + "$ "
    sys.stdout.write(promptLine)
    sys.stdout.flush()
    stdin = sys.stdin.readline()
    if len(stdin) == 0 or (len(stdin) >= 4 and stdin[0:4] == "exit"):
        print()
        sys.stdout.flush()
        sys.exit()
    elif stdin == "\n":
        print()
    elif len(stdin) >= 3 and stdin[0:2] == "cd" and stdin[2] in CMD_ENDERS:
        stdin.replace('~', HOMEDIR)
        stdin = stdin.split()
        if len(stdin)==1: #If nothing after cd
            os.chdir(HOMEDIR)
        else:
            os.chdir(stdin[1])
    elif len(stdin) >= 4 and stdin[0:4] == "jobs" and stdin[4] in CMD_ENDERS:
        for pid,cmd in bgJobs:
            print("[{}] {} running".format(pid, cmd))
    else:
        run(stdin.strip())

def childReaper(signum, frame):
    global outQueue, bgJobs, fgJobs
    print("Beginning Reaping")
    if (len(bgJobs) > 0) or (len(fgJobs) > 0):
        pid, status = os.waitpid(-1, os.WNOHANG)
        print("Returned From waitpid ", pid, status)
        if pid:
            if pid in fgJobs:
                if os.WEXITSTATUS(status):
                    outQueue.insert(0, "Command {} errored with exit status {}".format(fgJobs[pid], os.WEXITSTATUS(status)))
                print("Before Deleting fgJobs ", fgJobs)
                del fgJobs[pid]
                print("After Deleting fgJobs ", fgJobs)
            elif pid in bgJobs:
                outQueue.append("[{}] Command {} finished".format(pid, bgJobs[pid]))
                print("Before Deleting bgJobs ", bgJobs)
                del bgJobs[pid]
                print("After Deleting bgJobs ", bgJobs)
    print("Exit")

def main():
    global outQueue, bgJobs, fgJobs
    signal.signal(signal.SIGCHLD, childReaper)
    while True:
        prompt()

if __name__=="__main__":
    main()
