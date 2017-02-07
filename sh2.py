#/bin/env python3

import os, sys, signal, time

#CONSTANTS
CMD_ENDERS = (" ", "\n", "\t", ";", "&", "|", ">", "<")
HOMEDIR = os.getenv('HOME')

#GLOBALS
#A Dictionary of pid:[fg/bg(1/0 bool), original cmd]
gJobs = {}
#Buffers messages to print before prompt
gMessages = []

#Signal Handlers
def childReaper(signum, frame):
    global gMessages, gJobs
    while len(gJobs) > 0:
        try:
            pid, status = os.waitpid(0, os.WNOHANG)
        except:
            pass

        if not pid: #If no process needing to be reaped.
            break
        exit = os.WEXITSTATUS(status)
        signal = os.WTERMSIG(status)
        if gJobs[pid][0]: #If foreground
            if exit:
                gMessages.append("Error #{} in foreground job".format(exit))
                del gJobs[pid]
            elif signal:
                gMessages.append("Signal #{} in foreground job".format(signal))
                del gJobs[pid]
            elif os.WIFEXITED(status):
                del gJobs[pid]
            elif os.WIFSIGNALED(status):
                del gJobs[pid]
        else: #Background job
            gMessages.append("[{}] Command {} finished".format(pid, gJobs[pid][1]))
            if exit:
                gMessages.append("Error #{} in foreground job".format(exit))
                del gJobs[pid]
            elif signal:
                gMessages.append("Signal #{} in foreground job".format(signal))
                del gJobs[pid]
            elif os.WIFEXITED(status):
                del gJobs[pid]
            elif os.WIFSIGNALED(status):
                del gJobs[pid]


def childCrusher(signum, frame):
    global gJobs
    fgChildren = False
    for i in gJobs:
        if gJobs[i][0]:
            #If Foreground
            fgChildren = True
            try:
                pass#os.kill(i, signal.SIGINT) Have No Idea why this works
            except:
                pass

    #if not fgChildren:
    #    sys.exit()


#Main Basic Prompt Helpers
def blockFG():
    global gJobs

    fgJobs = True

    while fgJobs:
        #Only while jobs are still in foreground
        fgJobs = False
        #Loop over every job to make sure none are forground
        for pid, data in gJobs.items():
            if data[0]: #If the job is forground
                fgJobs = True #update the bool
                break #There is at least one fg job, so just wait for a change
        if fgJobs:
            time.sleep(1) #wait for something to change

def flushMessages():
    #Flush the Messages
    global gMessages

    for i in gMessages:
        print(i)
    sys.stdout.flush()

    gMessages = []

def printPrompt():
    sys.stdout.write(os.getcwd().replace(HOMEDIR, "~")+" $ ")
    sys.stdout.flush()

def localCommand(line):
    if len(line) == 0 or (len(line) >= 4 and line[0:4] == "exit" and line[4] in CMD_ENDERS):
        if len(line) == 0:
            print()
        sys.stdout.flush()
        sys.exit()
    elif len(line.strip()) == 0:
        return True
    elif len(line) >= 3 and line[0:2] == "cd" and line[2] in CMD_ENDERS:
        line.replace('~', HOMEDIR)
        line = line.split()
        if len(line) == 1:
            os.chdir(HOMEDIR)
        else:
            os.chdir(line[1])  #TODO: Add try/except
        return True
    elif len(line) >= 4 and line[0:4] == "jobs" and line[4] in CMD_ENDERS:
        for pid, pairs in gJobs.items():
            #100% sure it is bg, because otherwise would be blocked
            print("[{}] Running {}".format(pid, gJobs[pid][1]))
        return True


#Parse Functions. Use parse()
def breakPipes(cmds): #Break a string of commands by pipes
    returns = cmds.split('|')
    for i in range(len(returns)):
        returns[i] = returns[i].strip()
    return returns

def removeBg(cmd):
    bg = '&' in cmd
    return cmd.replace('&',''), bg

def removeFileIn(cmd):
    splitted = cmd.split('<')

    #If there is a file to capture, do it and move on
    if len(splitted) > 1:
        splitted[1] = splitted[1].strip()
        splitted = [splitted[0]] + splitted[1].split()
        fileIn = splitted[1].strip()
        del splitted[1]
    else:
        fileIn = None

    #Remove whitespace
    returns = []
    for i in range(len(splitted)):
        tmp = splitted[i].strip()
        if tmp:
            returns.append(tmp)

    # print('"', "".join(returns), '"', ' ', '"', fileIn,'"', sep="")
    return "".join(returns), fileIn

def removeFileOut(cmd):
    splitted = cmd.split('>')

    #If there is a file to capture, do it and move on
    if len(splitted) > 1:
        splitted[1] = splitted[1].strip()
        splitted = [splitted[0]] + splitted[1].split()
        fileOut = splitted[1].strip()
        del splitted[1]
    else:
        fileOut = None

    #Remove whitespace
    returns = []
    for i in range(len(splitted)):
        tmp = splitted[i].strip()
        if tmp:
            returns.append(tmp)

    # print('"', "".join(returns), '"', ' ', '"', fileOut,'"', sep="")
    return "".join(returns), fileOut

def splitCMD(cmd):
    return cmd.split()

def parse(cmd):
    orig = cmd
    output = []
    for part in breakPipes(cmd):
        part, bg = removeBg(part)
        part, filein = removeFileIn(part)
        part, fileout = removeFileOut(part)
        part = splitCMD(part)
        output.append([part[0], part, not bg, True, filein, fileout])
    output[-1][3] = False #Last item in the pipe chain isn't piped to nothing
    return output


def runProcess(cmd, args, read, write, closeMe=[]):
    pid = os.fork()
    if pid: #return the PID if parent
        return pid
    os.dup2(read, 0)
    os.close(read)
    os.dup2(write, 1)
    os.close(write)
    for i in closeMe:
        os.close(i)
    os.execvp(cmd, args)

def run(ParsedCMDs):
    global gJobs
    cur = 0
    nextReadPipe = None
    while ParsedCMDs[cur][3]:
        r, w = os.pipe()
        readFD = os.dup(0)
        writeFD = w
        if nextReadPipe is not None:
            readFD = nextReadPipe
        nextReadPipe = r

        if ParsedCMDs[cur][4] is not None:
            os.close(readFD)
            readFD = os.open(ParsedCMDs[cur][4], os.O_RDONLY)

        if ParsedCMDs[cur][5] is not None:
            os.close(writeFD)
            writeFD = os.open(ParsedCMDs[cur][5], os.O_CREAT | os.O_WRONLY | os.O_TRUNC)

        process = runProcess(ParsedCMDs[cur][0], #CMD
                             ParsedCMDs[cur][1], #CMD + Args
                             readFD, writeFD, closeMe=[nextReadPipe])
        os.close(readFD)
        os.close(writeFD)

        gJobs[process] = [ParsedCMDs[cur][2], ParsedCMDs[cur][1]]
        cur += 1

    readFD = os.dup(0)
    writeFD = os.dup(1)
    if nextReadPipe is not None:
        os.close(readFD)
        readFD = nextReadPipe

    if ParsedCMDs[cur][4] is not None:
        os.close(readFD)
        readFD = os.open(ParsedCMDs[cur][4], os.O_RDONLY)

    if ParsedCMDs[cur][5] is not None:
        os.close(writeFD)
        writeFD = os.open(ParsedCMDs[cur][5], os.O_CREAT | os.O_WRONLY | os.O_TRUNC)

    process = runProcess(ParsedCMDs[cur][0], #CMD
                            ParsedCMDs[cur][1], #CMD + Args
                            readFD, writeFD)

    gJobs[process] = [ParsedCMDs[cur][2], ParsedCMDs[cur][1]]

    os.close(readFD)
    os.close(writeFD)


def main():
    # global gJobs
    signal.signal(signal.SIGCHLD, childReaper)
    signal.signal(signal.SIGINT, childCrusher)
    while True:
        blockFG()
        flushMessages()
        printPrompt()
        line = sys.stdin.readline()
        if localCommand(line):
            continue
        parsed = parse(line)
        # print(parsed)
        try:
            run(parsed)
        except:
            print("Incorrect command")
        # print(gJobs)

if __name__ == "__main__":
    main()


