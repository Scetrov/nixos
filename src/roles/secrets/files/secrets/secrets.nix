let
  root = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJ4+AJpii7j0hNxwfVPnW+LVXBrp41GLZ4qjBZtC50mb";
  scetrov_hsm = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDB7n7NyXkm6OucNqS9ExJPUJk/+jhcIxTJD3RnEt2IywDvHWUOBBEcfpOxprj54UsJDrfAslIvhFZkjEi+3Tgow1qC7+HVS3GfNu1YCP+MmTOnnEXgAhtaM7LTVFgt9QYEZeSpgrIIaKSlb515ln4Ghy+Jehbs06V6TcJYG/qIQd1RXN40O13VEyXmNAVRSf9ra7Emfg1OLzu7wabhxLqeLGBJ2cf0QKf0+ip+jYqbq/D2ZsCBYmGgQcKiopuCW7a51zzu/Df6G+SJS2yzWwZx1PjJ0yqUFWpuVDlRJi2sBbBTL1TUftMzRiZsyQPrS/eAlGLxzGjmvjzZ3pLZtD5xc6Qs7By/r/5Acxbp+2wn3fuo6lVmD5P54R0PsQyw7jrV7C7Zb7Cl7EuXZqW3Pm42aowq4skstTmdXsZZx0RkFvFaxDw5IFtC78E5Dwy/4pECLNXQ8stc6A5MKElGwHhcABK8IdUGf6R0lU4yEzknb7KhvERZRKEslQh3Jcn+7zScc5WBbjT3SMEdySWPMwreOpe1gnt+6MSf/8lpQCyBOP1Mr4/SSa95pJpWyRr1OSPi0KgOvSTVwppG6thcV1fRpGsDtpPB192KKrzInP3fxF0UOT3PhLgn7zZAlyGBAIel4m/zK0tqjL3kG2CNwnOkMrq5CTdK1JS7KnK4a/rxCw==";
  scetrov_bastion = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDNIMu8cKsmBWtop3YBxx0b9u3FvefB/TZK6QNH9KPW4xBsxInvJlv+MC73cHd0aauEUJpgZnWY7/hqtfCn4hfIjhScHqTITyXFc7ngekWrhQfm3NOIGkU4wtVpTnwguBSg99CM62GEnd/yv8x9d7uLmn5fcnk6q0spYsgpF2ZsiMwomekHA0qntzJISzajbaqP42LvEG5HfaEZgWUwj7ajpgAG7hwdRvQFatpoX/CsMLGsQYctEQMUxaTF0deItv19l6B1Z74INx1LBJpoZ5FbQkLE/tJDP550UdtRTeP8GpzzZkh/6EdYvUu+O8X39Az0eWKWQR7rdS+xqeZRePxwU9K2bxoqD/IDfCw1hIBn3oGoGQ/Y759rD3+Ig5gbXZzGv5K0sYJHaAiFdMtPoE4GybH3J4Lnchujdiy7pbDaJaAA3SKuzcZwCM75LrO2JoFRJP8wrD71mnLHrStZVyykID3UB4kVeMsvJa8OmfR0DBaYSp8vMSs1WxeClZ+xl5cd71OChhkHvxDCsL/eb4k+Lyh35L+VOHHj/J85wuAAYjTgJtulcgcNIIGr60H7/jQmfxd7XzFaO7MJJ/MTu/yNYC4+//lSOwOYRrhaXwQuG5QCgW6EgCviUz5hHN1tUnVi5gh4vfm0bLMIQHuFBP6Q3e36n7IeWKsD+PhNZRPPDQ==";
  users = [ root scetrov_hsm scetrov_bastion ];

  devenv = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAID/F3dBtSPoouR5qVTHCJTsVVgPBFTFJB1WVxnUkvgKa";
  woodford = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIF6a5bYzqwYWOJ2ORbg4ANoALIGUfO2fVwLW9UyWfq50";
  systems = [ devenv woodford ];
in
{
  "scetrov_password.age".publicKeys = users ++ systems;
  "ssh_hsm_key.age".publicKeys = users ++ systems;
  "ssh_bastion_key.age".publicKeys = users ++ systems;
}