#!/usr/bin/perl
# -*- mode: perl; indent-tabs-mode: t; perl-indent-level: 8 -*-
# Author: Andrew Theurer

package PbenchAnsible;
use strict;
use warnings;
use File::Basename;
use Cwd 'abs_path';
use Exporter qw(import);
use List::Util qw(max);
use Data::Dumper;
use JSON;

our @EXPORT_OK = qw(ssh_hosts ping_hosts copy_files_to_hosts copy_files_from_hosts);

my $script = "PbenchAnsible.pm";
my $sub;
my $ansible_bin = "ansible";
my $ansible_playbook_bin = "ansible-playbook";
my $inventory_opt = " --inventory /var/lib/pbench-agent/ansible-hosts";
my $ansible_base_cmdline = $ansible_bin;
my $ansible_playbook_cmdline = $ansible_playbook_bin;

sub build_inventory {
	my $hosts_ref = shift;
	my $fh;
	my $file = `mktemp`;
	chomp $file;
	open($fh, ">", $file) or die "Could not create the inventory file";
	for my $h (@$hosts_ref) {
		print $fh "$h\n";
	}
	close $fh;
	return $file;
}
sub build_playbook {
	my $playbook_ref = shift;
	my $fh;
	my $file = `mktemp`;
	chomp $file;
	open($fh, ">", $file) or die "Could not create the playbook file";
	printf $fh "%s", to_json( $playbook_ref, { ascii => 1, pretty => 1, canonical => 1 } );
	close $fh;
	return $file;
}
sub ping_hosts {
	my $hosts_ref = shift;
	my $inv_file = build_inventory($hosts_ref);
	my $full_cmd = "ANSIBLE_CONFIG=/var/lib/pbench-agent/ansible.cfg " .
			$ansible_base_cmdline . " -i " .  $inv_file . " all -m ping";
	print "ansible cmdline:\n$full_cmd\n";
	my $output = `$full_cmd`;
	unlink $inv_file;
	return $output;
}
sub ssh_hosts {
	my $hosts_ref = shift;
	my $cmd = shift;
	my $inv_file = build_inventory($hosts_ref);
	my $full_cmd = "ANSIBLE_CONFIG=/var/lib/pbench-agent/ansible.cfg " .
			$ansible_base_cmdline . " -i " .  $inv_file . " all -a \"" . $cmd . "\"";
	print "ansible cmdline:\n$full_cmd\n";
	my $output = `$full_cmd`;
	unlink $inv_file;
	return $output;
}
sub copy_files_to_hosts { # copies local files to hosts with a new, common destination path
	my $hosts_ref = shift; # array-reference to host list
	my $src_files_ref = shift; # array-refernce to file list
	my $dst_path = shift; # a single destination path
	my $inv_file = build_inventory($hosts_ref);
	my @tasks;
	for my $src_file (@$src_files_ref) {
		my %task = ( name => "copy files to hosts", copy => "src=" . $src_file . " dest=" . $dst_path . "/" . basename($src_file) );
		push(@tasks, \%task);
	}
	my %play = ( hosts => "all", tasks => \@tasks );;
	my @playbook = (\%play);;
	my $playbook_file = build_playbook(\@playbook);
	my $full_cmd = "ANSIBLE_CONFIG=/var/lib/pbench-agent/ansible.cfg " .
			$ansible_playbook_cmdline . " -i " .  $inv_file . " " . $playbook_file;
	print "ansible cmdline:\n$full_cmd\n";
	my $output = `$full_cmd`;
	unlink $inv_file, $playbook_file;
	return $output;
}
sub copy_files_from_hosts { # copies local files to hosts with a new, common destination path
	my $hosts_ref = shift; # array-reference to host list to copy from 
	my $src_files_ref = shift; # array-refernce to file list to fetch
	my $src_path = shift; # a single src path where all files in list can be found
	my $inv_file = build_inventory($hosts_ref);
	my @tasks;
	for my $src_file (@$src_files_ref) {
		my %task = ( "name" => "copy files from hosts", "fetch" => "src=" . $src_path . "/" . $src_file . " dest=" . "/tmp/{{ inventory_hostname }}" );
		push(@tasks, \%task);
	}
	my %play = ( hosts => "all", tasks => \@tasks );;
	my @playbook = (\%play);;
	my $playbook_file = build_playbook(\@playbook);
	my $full_cmd = "ANSIBLE_CONFIG=/var/lib/pbench-agent/ansible.cfg " .
			$ansible_playbook_cmdline . " -i " .  $inv_file . " " . $playbook_file;
	print "ansible cmdline:\n$full_cmd\n";
	my $output = `$full_cmd`;
	unlink $inv_file, $playbook_file;
	return $output;
}


1;
