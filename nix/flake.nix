{
  description = "Ardent Forge — NixOS configuration for Bee Link";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    home-manager = {
      # Pinned to match dotfiles' home-manager; newer commits broke
      # programs.zsh.initContent (list-vs-string type change).
      url = "github:nix-community/home-manager/f4ad5068ee8e89e4a7c2e963e10dd35cd77b37b7";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Thomas's dotfiles for dev environment
    dotfiles = {
      url = "github:t-eckert/dotfiles";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, home-manager, dotfiles }:
    let
      # locals.nix is gitignored, so we import from an absolute path.
      # On the Bee Link this lives alongside the repo checkout.
      locals = import /data/ardent-forge/repo/nix/locals.nix;
    in {
    nixosConfigurations.ardent-forge = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      specialArgs = { inherit dotfiles locals; };
      modules = [
        ./hardware.nix
        ./configuration.nix
        home-manager.nixosModules.home-manager
        {
          home-manager = {
            useGlobalPkgs = true;
            useUserPackages = true;
            extraSpecialArgs = {
              inherit dotfiles locals;
              isDarwin = false;
              isLinux = true;
            };
            users.${locals.username} = import ./home.nix;
          };
        }
      ];
    };
  };
}
