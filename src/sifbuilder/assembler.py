import argparse
import datetime
import io
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Iterable

import argparser_adapter
import yaml
from argparser_adapter import ChoiceCommand, ArgparserAdapter
from sifbuilder import builder_logger

APPTAINER = Path('/usr/bin/apptainer')

_TEMPLATE = """BootStrap: localimage
From: {base} 

%post
	export DEBIAN_FRONTEND=noninteractive
	apt-get -qq update 
"""

_ENV = """%environment
    export LC_ALL=C"""

_EKEY = 'env'
_RKEY = 'run'
_LKEY = 'labels'
_HKEY = 'help'
_IKEY = 'install'

actionchoice = argparser_adapter.Choice("action", True, help='Action:')



class Builder:

    def __init__(self):
        """Parse local status for software. Read config value and determine debian packages to install"""
        self.force = False
        self.nolog = False

    def load(self,primary):
        """load configuration"""
        with open(primary) as f:
            aconfig = yaml.safe_load(f)
        self.base = Path(aconfig['base'])
        if not self.base.is_file():
            raise ValueError(f"Invalid base {self.base.as_posix()}")
        product = aconfig['product']
        self.defpath = Path(product + '.def')
        self.sifpath = Path(product + '.sif')
        self.apps = {}

    def _set_path(self,current:Path,config,key)->Path:
        if (v := config.get(key)) is not None:
            vpath = Path(v)
            if current is None or current == v:
                return v
        return current


    def configure(self,yamls:Iterable[str|Path]):
        paths = [Path(y) for y in yamls]
        bad = [m for m in paths if not m.is_file()]
        if bad:
            raise ValueError(f"Missing yaml file {','.join(bad)}")
        configs = []
        for p in paths:
            builder_logger.debug(f"Evaluate {p.as_posix()}")
            try:
                with open(p) as f:
                    dc = yaml.safe_load(f)
                    if dc.get('sifassembly',False):
                        builder_logger.info(f"Reading {p.as_posix()}")
                        configs.append(dc)
            except Exception as e:
                builder_logger.info(f"Fail to parse {p.as_posix()} {e}")
        ordered = {c['app']:c for c in configs}
        for appname in sorted(ordered.keys()):
            app_cfg = ordered[appname]
            app = app_cfg['app']
            self.apps[app] = (app_d := {})
            pkgs = app_cfg.get('packages',None)
            f: io.StringIO
            if pkgs:
                with io.StringIO() as f:
                    print(f"    apt-get -qq install {' '.join(pkgs)}",file=f)
                    app_d[_IKEY] = f.getvalue()

            edict = app_cfg.get("environment", {})
            if edict:
                with io.StringIO() as f:
                    for env, value in edict.get('append', {}).items():
                        print(f'    export {env}=${env}:{value}', file=f)
                    app_d[_EKEY] = f.getvalue()
            if (rlist :=  app_cfg.get("run", [])):
                with io.StringIO() as f:
                    for cmd in rlist:
                        print(f'    {cmd}', file=f)
                    app_d[_RKEY] = f.getvalue()
            labels = app_cfg.get("labels", {})
            if labels:
                with io.StringIO() as f:
                    for env, value in labels.items() :
                        print(f'    {env} {value}', file=f)
                    app_d[_LKEY] = f.getvalue()
            help = app_cfg.get('help',[])
            if help:
                with io.StringIO() as f:
                    for h in help:
                        print(f'    {h}', file=f)
                    app_d[_HKEY] = f.getvalue()


    @ChoiceCommand(actionchoice)
    def generate(self):
        """generate def file"""
        if self.defpath.exists() and not self.force:
            raise ValueError(f"{self.defpath.as_posix()} already present")
        builder_logger.info(f"generating {self.defpath.as_posix}")
        with open(self.defpath, 'w') as f:
            print(_TEMPLATE.format(base=self.base), file=f)
            self._add_enviroment(f)
            for app,data in self.apps.items():
                for scifkey in (_IKEY, _RKEY,_LKEY,_EKEY,_HKEY):
                    if (stanza := data.get(scifkey,None)) is not None:
                        print(f'\n%app{scifkey} {app}',file=f)
                        print(stanza,file=f)
            self.__add_runscript(f)
        print(f"Wrote {self.defpath}")

    def _add_enviroment(self, f):
        """Add environment setting from config, if any"""
        print(_ENV, file=f)

    def __add_runscript(self,f):
        return
        runlist= self.config.get("run",[])
        if runlist:
            print('\n%runscript',file=f)
            for cmd in runlist:
                print(f'   {cmd} ',file=f)

    def _check_paths(self):
        """Check paths, raise error or overwrite, depending on self.force"""
        if not APPTAINER.is_file():
            raise ValueError(f"{APPTAINER.as_posix()} not found. Install apptainer debian package")
        if not self.defpath.is_file() or self.force:
            self.generate()
        if self.sifpath.exists():
            if not self.force:
                raise ValueError(f"{self.sifpath.as_posix()} already present")
            if self.sifpath.is_dir():
                shutil.rmtree(self.sifpath)
            else:
                self.sifpath.unlink()
        self.sifpath.parent.mkdir(exist_ok=True)

    def _run(self, cmd_i):
        """Run a command after displaying to user"""
        cmd = [item.as_posix() if isinstance(item, Path) else item for item in cmd_i]
        print(f"Running: {' '.join(cmd)}")
        if self.nolog:
            subprocess.run(cmd)
        else:
            sname = self.sifpath.name
            ts = datetime.datetime.now().strftime(f"{sname}-%b%d-%H:%M:%S.log")
            with open(ts, 'w') as logfile:
                print(f"logging to {logfile.name}")
                subprocess.run(cmd, stdout=logfile, stderr=subprocess.STDOUT)

    @ChoiceCommand(actionchoice)
    def sif(self):
        """Build single sif from def file"""
        self._check_paths()
        self._run((APPTAINER, 'build', self.sifpath, self.defpath))

    @ChoiceCommand(actionchoice)
    def sandbox(self):
        """Build writable sandbox directory from def file"""
        self._check_paths()
        self._run((APPTAINER, 'build', '--sandbox', self.sifpath, self.defpath))


@dataclass
class ParseSpec:
    directories: Iterable[str]
    depth: int

@dataclass
class ParseOut:
    yamls: Iterable[Path]


class _DirectoryParser:

    def __init__(self,p:ParseSpec):
        self.spec = p
        self.yamls : List[Path] = []

    def _parse(self,directories,depth):
        for dpath in directories:
            if not dpath.is_dir():
                raise ValueError(f"{dpath.as_posix()} is not a directory")
            for p in Path(dpath).glob('*yaml'):
                self.yamls.append(p)
            if depth > 0:
                subs = [d for d in dpath.iterdir() if d.is_dir()]
                self._parse(subs,depth-1)

    def parse(self):
        dpaths = [Path(d) for d in self.spec.directories]
        self._parse(dpaths,self.spec.depth)
        return self.yamls



def main():
    logging.basicConfig()
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('primary',help="primary configuration file")
    builder = Builder()
    adapter = ArgparserAdapter(builder)
    adapter.register(parser)
    parser.add_argument('-d','--directory',action='append',help= "Directory to scan for yamls")
    parser.add_argument('--depth' ,type=int,default=0,help="How far to descond into directories looking for yamls")
    parser.add_argument('-l', '--loglevel', default='WARN', help="Python logging level")
    parser.add_argument('--force', action='store_true', help="Overwrite existing def and sif")
    parser.add_argument('--nolog', action='store_true', help="Apptainer output to stdout/stderr instead of log files")

    args = parser.parse_args()
    builder_logger.setLevel(getattr(logging, args.loglevel))
    builder.force = args.force
    builder.nolog = args.nolog
    builder.load(args.primary)
    dp = _DirectoryParser(ParseSpec(args.directory,args.depth))
    yamls = dp.parse()
    builder.configure(yamls)

    adapter.call_specified_methods(args)


if __name__ == "__main__":
    main()
