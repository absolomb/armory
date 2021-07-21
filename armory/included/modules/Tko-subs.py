#!/usr/bin/python
from armory.database.repositories import DomainRepository
from ..ModuleTemplate import ToolTemplate
from ..utilities.color_display import display_new, display_warning
import os


class Module(ToolTemplate):
    """
    This tool will check various subdomains for domain takeover vulnerabilities.
    """

    name = "Tko-subs"
    binary_name = "tko-subs"

    def __init__(self, db):
        self.db = db
        self.Domain = DomainRepository(db, self.name)

    def set_options(self):
        super(Module, self).set_options()

        self.options.add_argument("--data", help="Path to the providers_data.csv file")
        self.options.add_argument(
            "-d", "--domain", help="Domain to run the tool against."
        )
        self.options.add_argument(
            "-i",
            "--importdb",
            help="Import subdomains from the database.",
            action="store_true",
        )
        self.options.add_argument(
            "--rescan", help="Rescan already processed entries", action="store_true"
        )

    def get_targets(self, args):
        """
        This module is used to build out a target list and output file list, depending on the arguments. Should return a
        list in the format [{'target':target, 'output':output}, {'target':target, 'output':output}, etc, etc]
        """

        # Create an empty list to add targets to
        domains = []

        # Check if a domain has been explicitly passed, and if so add it to targets
        if args.domain:
            domains.append(args.domain)

        # Check if the --import option was passed  and if so get data from the domain.
        # The scoping is set to "active" since the tool could potentially make a
        # request from the server.

        if args.importdb:
            if args.rescan:
                all_domains = self.Domain.all(scope_type="active")
            else:
                all_domains = self.Domain.all(scope_type="active", tool=self.name)
            for d in all_domains:
                domains.append(d.domain)

        # Set the output_path base, as a junction of the base_path and the path name supplied
        if args.output_path[0] == "/":
            output_path = os.path.join(
                self.base_config["PROJECT"]["base_path"], args.output_path[1:]
            )
        else:
            output_path = os.path.join(
                self.base_config["PROJECT"]["base_path"], args.output_path
            )

        # Create the path if it doesn't already exist
        if not os.path.exists(output_path):
            os.makedirs(output_path)

        res = []

        # Create the final targets list, with output paths added.
        for d in domains:
            res.append({"target": d, "output": os.path.join(output_path, d)})

        return res

    def build_cmd(self, args):
        """
        Create the actual command that will be executed. Use {target} and {output} as placeholders.
        """
        cmd = self.binary + " -domain {target}  -output {output} "

        # Add in any extra arguments passed in the extra_args parameter
        if args.tool_args:
            cmd += args.tool_args
        # Add that data parameter in there
        if not args.data:
            args.data = os.path.join(os.path.dirname(self.binary), 'providers-data.csv')

        cmd += " -data " + args.data
        return cmd

    def process_output(self, cmds):
        """
        Process the output generated by the earlier commands.
        """

        # Cycle through all of the targets we ran earlier
        for c in cmds:

            output_file = c["output"]
            target = c["target"]

            # Read file
            data = open(output_file).read().split("\n")

            # Quick and dirty way to filter out headers and blank lines, as well
            # as duplicates
            res = list(set([d for d in data if "Domain,Cname,Provider" not in d and d]))
            if res:
                # Load up the DB entry.
                created, subdomain = self.Domain.find_or_create(domain=target)

                # Process results
                for d in res:
                    results = d.split(",")

                    if results[3] == "false":
                        display_warning(
                            "Hosting found at {} for {}, not vulnerable.".format(
                                target, results[2]
                            )
                        )

                    elif results[3] == "true":
                        display_new("{} vulnerable to {}!".format(target, results[2]))
                        if not subdomain.meta[self.name].get("vulnerable", False):
                            subdomain.meta[self.name]["vulnerable"] = []
                        subdomain.meta[self.name]["vulnerable"].append(d)

                    else:
                        display_warning("Not sure of result: {}".format(data))

                # This is a little hackish, but needed to get data to save
                t = dict(subdomain.meta)
                self.Domain.commit()
                subdomain.meta = t

        self.Domain.commit()