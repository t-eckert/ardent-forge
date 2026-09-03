{
  description = "Ardent Forge — NixOS configuration for Bee Link";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Thomas's dotfiles for dev environment
    dotfiles = {
      url = "github:t-eckert/dotfiles";
      inputs.nixpkgs.follows = "nixpkgs";
      # hunk pins its own nixpkgs, which pulled a second full nixpkgs into the
      # closure and evaluated it for x86_64-darwin -- emitting that release's
      # deprecation warning on every rebuild of this Linux box. Upstream notes
      # it cannot suppress this for transitive inputs, so the fix is to stop
      # having a transitive nixpkgs at all. Deduping it also removes a second
      # source tree from evaluation.
      inputs.hunk.inputs.nixpkgs.follows = "nixpkgs";
      # Deduping alone is not enough: hunk hardcodes x86_64-darwin in its own
      # supportedSystems, and bun2nix (via flake-parts) forces every system in
      # its `systems` input. Against nixpkgs 26.05 that only warned; against
      # ours it is a hard error, because 26.11 dropped x86_64-darwin outright.
      # Narrowing that input to this machine's system stops darwin from being
      # instantiated at all, which is what makes the follows above viable.
      inputs.hunk.inputs.bun2nix.inputs.systems.follows = "systems-linux";
    };

    # Pins flake-parts' system enumeration for the inputs above. Nothing else
    # should follow this -- it exists to keep a transitive dependency from
    # evaluating platforms this machine will never build for.
    systems-linux = {
      url = "github:nix-systems/x86_64-linux";
    };
  };

  # systems-linux is declared purely to be followed by a transitive input; it
  # is never referenced here, hence the ellipsis.
  outputs = { self, nixpkgs, home-manager, dotfiles, ... }:
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
              self = dotfiles;  # allows packages.nix to resolve dotfiles-tools
              hunk = dotfiles.inputs.hunk;  # dotfiles' packages.nix pulls hunk from its own inputs
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
